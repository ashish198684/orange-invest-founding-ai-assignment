"""Test-first: roles and transaction separation, not a shared atomic mock."""
import unittest
from app.runtime.pg import PgStore
from app.runtime.provider_client import ProviderClient
from app.workflow import WorkflowController

class FaultBoundary(unittest.TestCase):
    def test_authority_role_cannot_read_or_write_provider(self):
        store=PgStore('test-alice')
        with self.assertRaises(Exception):
            with store.connect() as db: db.execute('SELECT * FROM provider.provider_bookings')
        with self.assertRaises(Exception):
            with store.connect(write=True) as db: db.execute('DELETE FROM provider.provider_bookings')

    def test_client_has_exact_eight_signatures_and_no_provider_db(self):
        import inspect
        expected={'search_providers':['service','area','date_range'],'get_provider':['provider_id'],
          'list_bookings':['user_id'],'hold_slot':['provider_id','slot'],'book':['hold_id','idempotency_key'],
          'get_booking_status':['idempotency_key'],'cancel':['booking_id','idempotency_key'],
          'reschedule':['booking_id','new_slot','idempotency_key']}
        public={n for n,f in inspect.getmembers(ProviderClient,inspect.isfunction) if not n.startswith('_')}
        self.assertEqual(public,set(expected))
        for name,params in expected.items():
            self.assertEqual(list(inspect.signature(getattr(ProviderClient,name)).parameters),['self',*params])
        self.assertFalse(hasattr(ProviderClient('test-alice'),'store'))
