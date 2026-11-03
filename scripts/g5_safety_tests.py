"""G5 additional security/regression tests; no dependence on a live LLM."""
import json,os,tempfile,unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app.runtime.security import allowed_origin,check_csrf,hashed
from app.runtime.provider_client import sanitized_tool_arguments
from app.runtime.observe import Run

class G5HardeningTests(unittest.TestCase):
    def test_default_origin_only(self):
        with patch.dict(os.environ,{'ORANGE_ADDITIONAL_LOOPBACK_ORIGIN':''}):
            for port in (8080,8081,8082):
                self.assertTrue(allowed_origin('http://127.0.0.1:'+str(port)))
            for origin in ('http://127.0.0.1:8181','https://evil.example','null',
                           'http://localhost:8181','http://127.0.0.2:8080'):
                self.assertFalse(allowed_origin(origin))

    def test_exact_test_loopback_override_and_csrf(self):
        with patch.dict(os.environ,{'ORANGE_ADDITIONAL_LOOPBACK_ORIGIN':'http://127.0.0.1:8181'}):
            self.assertTrue(allowed_origin('http://127.0.0.1:8181'))
            self.assertFalse(allowed_origin('http://127.0.0.1:8182'))
            self.assertFalse(allowed_origin('http://127.0.0.1:8181.evil.com'))
            token='synthetic-csrf'
            check_csrf({'csrf_hash':hashed(token)},token,'http://127.0.0.1:8181')
            with self.assertRaises(PermissionError):
                check_csrf({'csrf_hash':hashed(token)},token,'http://127.0.0.1:8182')
            with self.assertRaises(PermissionError):
                check_csrf({'csrf_hash':hashed(token)},'wrong','http://127.0.0.1:8181')

    def test_override_does_not_expand_to_other_hosts(self):
        for bad in ('https://127.0.0.1:8181','http://evil.example:8181',
                    'http://127.0.0.1:8181/extra','http://127.0.0.1:0'):
            with patch.dict(os.environ,{'ORANGE_ADDITIONAL_LOOPBACK_ORIGIN':bad}):
                self.assertFalse(allowed_origin(bad))

    def test_all_eight_fixed_tools_have_safe_typed_argument_evidence(self):
        date={'start':'2026-11-04T00:00:00+05:30','end':'2026-11-09T00:00:00+05:30'}
        raw_key='very-sensitive-operation-key-456'
        cases={
            'search_providers':('plumber','Indiranagar',date),
            'get_provider':('plumber-0-0',),
            'list_bookings':('synthetic-private-user',),
            'hold_slot':('plumber-0-0','2026-11-04T09:00:00+05:30'),
            'book':('sensitive-hold-id-abc',raw_key),
            'get_booking_status':(raw_key,),
            'cancel':('sensitive-booking-id-abc',raw_key),
            'reschedule':('sensitive-booking-id-abc','2026-11-05T11:00:00+05:30',raw_key)
        }
        for method,args in cases.items():
            with self.subTest(tool=method):
                value=sanitized_tool_arguments(method,args)
                self.assertEqual(value['argument_count'],len(args))
                self.assertEqual(len(value['payload_sha256']),64)
                self.assertGreater(len(value),2)
                encoded=json.dumps(value)
                self.assertNotIn(raw_key,encoded)
                self.assertNotIn('sensitive-hold-id',encoded)
                self.assertNotIn('sensitive-booking-id',encoded)
                self.assertNotIn('synthetic-private-user',encoded)
        self.assertEqual(sanitized_tool_arguments('search_providers',cases['search_providers'])['area'],'Indiranagar')
        self.assertIn('idempotency_key_sha256',sanitized_tool_arguments('get_booking_status',cases['get_booking_status']))

    def test_trace_filter_keeps_whitelist_and_drops_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ,{'RUNTIME_STATE':temp}):
                row=Run('test-user').emit('provider_start',tool='book',
                    sanitized_args={'argument_count':2,'hold_id_sha256':'a'*64,
                                    'idempotency_key_sha256':'b'*64,
                                    'raw_secret':'gsk_should_never_enter_traces'})
                self.assertEqual(row['sanitized_args']['hold_id_sha256'],'a'*64)
                self.assertNotIn('raw_secret',row['sanitized_args'])
                saved=(Path(temp)/'traces'/(row['run_id']+'.jsonl')).read_text()
                self.assertNotIn('gsk_should_never_enter_traces',saved)

if __name__=='__main__':
    unittest.main(verbosity=2)
