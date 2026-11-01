"""G2 controller/provider acceptance. These are not the G4 scripted-user evals."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest

from app.provider_mock import ProviderMock, ProviderError, ScenarioConfig
from app.workflow import WorkflowController, SafetyError

NOW = datetime.fromisoformat('2026-11-01T09:00:00+05:30')
WINDOW = {'start': NOW.isoformat(), 'end': (NOW + timedelta(days=8)).isoformat()}

class Clock:
    value = NOW
    def __call__(self):
        return self.value

class AuditProvider:
    def __init__(self, provider):
        self.inner = provider
        self.calls = []
        self.fault = None

    def __getattr__(self, name):
        value = getattr(self.inner, name)
        if not callable(value) or name.startswith('_'):
            return value
        def call(*args):
            event = {'tool': name, 'args': args}
            self.calls.append(event)
            try:
                if self.fault:
                    self.fault(name, args)
                result = value(*args)
                event['result'] = result
                return result
            except Exception as exc:
                event['error'] = type(exc).__name__
                raise
        return call

class G2SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.sqlite3'
        self.clock = Clock()
        self.p = None
        self.c = None

    def setup_controller(self, branch='book_success', *, delta=0, conflicts=()):
        p = ProviderMock(self.path, user_id='alice', clock=self.clock,
                         config=ScenarioConfig(book_branch=branch, quote_delta=delta,
                                               reschedule_conflicts=conflicts))
        self.p = AuditProvider(p)
        self.c = WorkflowController(self.path, user_id='alice', clock=self.clock, provider=self.p)
        return self.c

    def request(self, key='request-1', **changes):
        fields = dict(service='plumber', area='Indiranagar', date_window=WINDOW, budget_inr=1500)
        fields.update(changes)
        return self.c.create_request(key, **fields)['workflow_id']

    def approval(self, key='request-1', index=0):
        wid = self.request(key)
        option = self.c.search(wid)[0]
        return wid, self.c.prepare_booking(wid, option['id'], option['free_slots'][index])

    def booked(self):
        wid, a = self.approval()
        result = self.c.confirm(wid, a['approval_id'])
        self.assertEqual(result['status'], 'BOOKED')
        return wid, result

    def deny(self, code, function):
        with self.assertRaises(SafetyError) as exc:
            function()
        self.assertEqual(exc.exception.code, code)

    def rows(self, table):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute('SELECT * FROM '+table)]

    def tearDown(self):
        target = os.environ.get('G2_EVIDENCE_DIR')
        if target and self.path.exists():
            out = Path(target)/self._testMethodName
            out.mkdir(parents=True, exist_ok=False)
            # SQLite backup yields a self-contained DB independent of WAL lifecycle.
            with closing(sqlite3.connect(self.path)) as src, closing(sqlite3.connect(out/'state.sqlite3')) as dest:
                src.backup(dest)
                names = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            snapshot = {name: self.rows(name) for name in names}
            (out/'database.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
            (out/'provider_calls.json').write_text(json.dumps(self.p.calls if self.p else [],indent=2)+'\n',encoding='utf-8')

    def test_missing_fields_and_correction_preserve_constraints(self):
        c = self.setup_controller()
        w = c.create_request('draft', service='plumber')
        self.assertEqual(c.next_question(w['workflow_id'])['field'], 'area')
        c.correct(w['workflow_id'], area='Indiranagar', date_window=WINDOW, budget_inr=1500,
                  preferences={'earliest_hour':10})
        old = c.view(w['workflow_id'])
        new = c.correct(w['workflow_id'], area='Koramangala')
        self.assertGreater(new['revision'], old['revision'])
        self.assertEqual(new['draft']['budget_inr'],1500)
        self.assertEqual(new['draft']['service'],'plumber')
        self.assertEqual(new['draft']['preferences'],{'earliest_hour':10})
        self.assertIsNone(c.next_question(w['workflow_id']))

    def test_scripted_chat_extracts_and_preserves_without_granting(self):
        c = self.setup_controller()
        wid = c.create_request('chat')['workflow_id']
        c.chat(wid, 'Find a plumber in Indiranagar this week, mornings only, under 1500')
        v = c.view(wid)
        self.assertEqual(v['draft']['service'],'plumber')
        self.assertEqual(v['draft']['budget_inr'],1500)
        self.assertEqual(v['draft']['date_window']['end'],'2026-11-02T00:00:00+05:30')
        c.chat(wid,'Actually Koramangala')
        self.assertEqual(c.view(wid)['draft']['service'],'plumber')
        self.assertEqual(c.view(wid)['draft']['area'],'Koramangala')
        self.deny('approval_required',lambda:c.chat(wid,'yes'))
        self.assertFalse(self.rows('provider_bookings'))

    def test_relative_saturday_uses_injected_clock(self):
        c=self.setup_controller()
        wid=c.create_request('saturday')['workflow_id']
        c.chat(wid,'plumber Indiranagar Saturday')
        window=c.view(wid)['draft']['date_window']
        self.assertEqual(window['start'],'2026-11-07T00:00:00+05:30')
        self.assertEqual(window['end'],'2026-11-08T00:00:00+05:30')

    def test_absent_model_approval_and_unbound_yes_deny_all_writes(self):
        c=self.setup_controller()
        wid,a=self.approval()
        self.deny('approval_required',lambda:c.confirm(wid,None))
        self.deny('untrusted_fields',lambda:c.propose(wid,{'approved':True,'tool':'book'}))
        self.deny('approval_required',lambda:c.chat(wid,'yes'))
        self.deny('forbidden',lambda:c.execute('invented-operation'))
        self.assertFalse(self.rows('provider_bookings'))
        self.assertFalse(self.rows('operations'))

    def test_exact_immutable_approval_and_operation_bindings(self):
        c=self.setup_controller(delta=250)
        wid,a=self.approval()
        s=a['snapshot']
        self.assertEqual(s['price_amount'],1150)
        self.assertEqual(s['price_status'],'hold_quote')
        for key in ['user_id','workflow_id','action','booking_id','provider_id','old_slot','new_slot',
                    'hold_id','revision','expires_at','original_price','new_price_status']:
            self.assertIn(key,s)
        op=c.grant_approval(wid,a['approval_id'])
        row=self.rows('operations')[0]
        self.assertEqual(row['operation_id'],op)
        self.assertEqual(row['payload_fingerprint'],a['fingerprint'])
        self.assertEqual(json.loads(row['snapshot_json']),s)
        with self.assertRaises(sqlite3.IntegrityError):
            with closing(sqlite3.connect(self.path)) as db:
                db.execute("UPDATE approval_snapshots SET snapshot_json='{}'")
        with self.assertRaises(sqlite3.IntegrityError):
            with closing(sqlite3.connect(self.path)) as db:
                db.execute("UPDATE operations SET idempotency_key='replacement'")
        self.assertEqual(c.execute(op)['status'],'BOOKED')

    def test_budget_exceeded_has_no_approvable_quote(self):
        c=self.setup_controller(delta=700)
        wid=self.request()
        p=c.search(wid)[0]
        self.deny('budget_exceeded',lambda:c.prepare_booking(wid,p['id'],p['free_slots'][0]))
        self.assertFalse(self.rows('approval_snapshots'))
        self.assertFalse(self.rows('provider_bookings'))

    def test_changed_provider_slot_budget_and_aba_void_old_approval(self):
        c=self.setup_controller()
        wid,a=self.approval()
        original=c.view(wid)['draft']['area']
        c.correct(wid,area='Koramangala')
        c.correct(wid,area=original)
        self.deny('approval_invalid',lambda:c.confirm(wid,a['approval_id']))
        self.assertFalse(self.rows('provider_bookings'))
        for index,(field,value) in enumerate([('provider_id','plumber-0-1'),('slot','2026-11-03T09:00:00+05:30'),('budget_inr',1200)],1):
            with self.subTest(field=field):
                wid,a=self.approval(field,index=index)
                c.correct(wid,**{field:value})
                self.deny('approval_invalid',lambda:c.confirm(wid,a['approval_id']))

    def test_stale_hold_quote_tampering_denied(self):
        c=self.setup_controller()
        wid,a=self.approval()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE workflow_holds SET quoted_price=quoted_price+1')
            db.commit()
        self.deny('approval_invalid',lambda:c.confirm(wid,a['approval_id']))
        self.assertFalse(self.rows('provider_bookings'))

    def test_fresh_selection_with_changed_quote_voids_previous_card(self):
        c=self.setup_controller(delta=100)
        wid,a=self.approval()
        b=c.prepare_booking(wid,'plumber-0-1','2026-11-02T11:00:00+05:30')
        self.assertEqual(a['snapshot']['price_amount'],1000)
        self.assertEqual(b['snapshot']['price_amount'],1300)
        self.assertGreater(b['snapshot']['revision'],a['snapshot']['revision'])
        self.deny('approval_invalid',lambda:c.confirm(wid,a['approval_id']))
        result=c.confirm(wid,b['approval_id'])
        self.assertEqual(result['booking']['provider'],'plumber-0-1')
        self.assertEqual(self.rows('provider_bookings')[0]['quoted_price'],1300)

    def test_hold_ttl_boundary_599_and_600_seconds(self):
        c=self.setup_controller()
        wid,a=self.approval()
        self.assertEqual(datetime.fromisoformat(a['snapshot']['expires_at'])-NOW,timedelta(minutes=10))
        self.clock.value=NOW+timedelta(seconds=600)
        self.deny('approval_expired',lambda:c.confirm(wid,a['approval_id']))
        fresh=c.prepare_booking(wid,a['snapshot']['provider_id'],a['snapshot']['new_slot'])
        self.assertNotEqual(fresh['approval_id'],a['approval_id'])
        self.clock.value+=timedelta(seconds=599)
        self.assertEqual(c.confirm(wid,fresh['approval_id'])['status'],'BOOKED')

    def test_expired_granted_hold_does_not_execute(self):
        c=self.setup_controller()
        wid,a=self.approval()
        op=c.grant_approval(wid,a['approval_id'])
        self.clock.value+=timedelta(minutes=10)
        self.assertEqual(c.execute(op)['status'],'NEEDS_REAPPROVAL')
        self.assertFalse(self.rows('provider_bookings'))

    def test_verified_booking_duplicate_confirmation_and_transport_retry(self):
        c=self.setup_controller()
        wid,a=self.approval()
        first=c.confirm(wid,a['approval_id'])
        second=c.confirm(wid,a['approval_id'])
        self.assertEqual(first['booking_id'],second['booking_id'])
        self.assertEqual(first['operation_id'],second['operation_id'])
        self.assertEqual(first['status'],'BOOKED')
        self.assertEqual(len(self.rows('provider_bookings')),1)
        self.assertEqual(len(self.rows('operations')),1)
        self.assertEqual(self.request(),wid)

    def test_logical_request_cannot_book_second_slot_or_replace_unknown(self):
        c=self.setup_controller('timeout_without_booking')
        wid,a=self.approval()
        self.assertEqual(c.confirm(wid,a['approval_id'])['status'],'OUTCOME_UNKNOWN')
        self.deny('request_locked',lambda:c.correct(wid,slot='2026-11-03T11:00:00+05:30'))
        self.deny('request_locked',lambda:c.prepare_booking(wid,'plumber-0-1','2026-11-03T11:00:00+05:30'))
        self.deny('logical_request_mismatch',lambda:c.create_request('request-1',service='electrician'))
        self.assertEqual(len(self.rows('operations')),1)
        self.assertFalse(self.rows('provider_bookings'))

    def test_booked_logical_request_cannot_create_fresh_booking(self):
        c=self.setup_controller()
        wid,result=self.booked()
        self.deny('request_locked',lambda:c.prepare_booking(wid,'plumber-0-1','2026-11-03T11:00:00+05:30'))
        self.assertEqual(len(self.rows('provider_bookings')),1)

    def test_two_connections_concurrent_confirmations_one_booking(self):
        c=self.setup_controller()
        wid,a=self.approval()
        other=WorkflowController(self.path,user_id='alice',clock=self.clock)
        barrier=Barrier(2)
        def run(controller):
            barrier.wait()
            return controller.confirm(wid,a['approval_id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,[c,other]))
        self.assertEqual(results[0]['booking_id'],results[1]['booking_id'])
        self.assertEqual(len(self.rows('operations')),1)
        self.assertEqual(len(self.rows('provider_bookings')),1)

    def test_cross_user_workflow_approval_and_operation_denied(self):
        c=self.setup_controller()
        wid,a=self.approval()
        op=c.grant_approval(wid,a['approval_id'])
        other=WorkflowController(self.path,user_id='bob',clock=self.clock)
        for fn in [lambda:other.view(wid),lambda:other.confirm(wid,a['approval_id']),
                   lambda:other.execute(op),lambda:other.correct(wid,area='Koramangala')]:
            self.deny('forbidden',fn)
        bw=other.create_request('request-1',service='plumber',area='Indiranagar',date_window=WINDOW)['workflow_id']
        self.deny('approval_invalid',lambda:other.confirm(bw,a['approval_id']))
        self.assertFalse(self.rows('provider_bookings'))

    def test_provider_context_mismatch_and_client_identity_rejected(self):
        c=self.setup_controller()
        with self.assertRaises(SafetyError):
            WorkflowController(self.path,user_id='bob',clock=self.clock,provider=self.p)
        wid=self.request()
        self.deny('untrusted_fields',lambda:c.propose(wid,{'user_id':'admin'}))
        self.deny('untrusted_fields',lambda:c.correct(wid,user_id='admin'))
        self.assertFalse(self.rows('provider_bookings'))

    def test_review_injection_quarantined_no_permission_or_intent_change(self):
        c=self.setup_controller()
        wid,a=self.approval()
        before=c.view(wid)
        detail=c.details(a['snapshot']['provider_id'])
        self.assertTrue(any('SYSTEM' in r['text'] for r in detail['reviews']))
        for review in detail['reviews']:
            self.assertEqual(review['trust'],'untrusted')
            self.assertEqual(review['source'],'provider_review')
        self.assertEqual(c.view(wid),before)
        self.assertFalse(self.rows('provider_bookings'))
        self.assertFalse(self.rows('operations'))

    def test_timeout_after_success_status_before_any_retry_and_verified_message(self):
        c=self.setup_controller('timeout_after_success')
        wid,a=self.approval()
        r=c.confirm(wid,a['approval_id'])
        self.assertEqual(r['status'],'BOOKED')
        self.assertIn('verified',r['message'].lower())
        tools=[x['tool'] for x in self.p.calls]
        i=tools.index('book')
        self.assertEqual(tools[i+1],'get_booking_status')
        self.assertEqual(tools.count('book'),1)
        self.assertEqual(self.rows('provider_bookings')[0]['id'],r['booking_id'])
        self.assertEqual(self.rows('operations')[0]['status'],'COMMITTED')

    def test_timeout_without_booking_is_bounded_across_restarts(self):
        c=self.setup_controller('timeout_without_booking')
        wid,a=self.approval()
        first=c.confirm(wid,a['approval_id'])
        self.assertEqual(first['status'],'OUTCOME_UNKNOWN')
        self.assertIn('unverified',first['message'].lower())
        calls=[x for x in self.p.calls if x['tool']=='book']
        self.assertEqual(len(calls),3)
        self.assertEqual(len({x['args'][1] for x in calls}),1)
        tools=[x['tool'] for x in self.p.calls]
        for i,name in enumerate(tools):
            if name=='book': self.assertEqual(tools[i+1],'get_booking_status')
        fresh=WorkflowController(self.path,user_id='alice',clock=self.clock)
        self.assertEqual(fresh.confirm(wid,a['approval_id'])['status'],'OUTCOME_UNKNOWN')
        self.assertEqual(self.rows('operations')[0]['attempts'],3)
        self.assertFalse(self.rows('provider_bookings'))

    def test_restart_pending_operation_before_first_provider_write(self):
        c=self.setup_controller()
        wid,a=self.approval()
        op=c.grant_approval(wid,a['approval_id'])
        self.assertFalse(self.rows('provider_bookings'))
        fresh=WorkflowController(self.path,user_id='alice',clock=self.clock)
        self.assertEqual(fresh.recover()[0]['status'],'BOOKED')
        self.assertEqual(fresh.execute(op)['booking_id'],self.rows('provider_bookings')[0]['id'])
        self.assertEqual(len(self.rows('provider_bookings')),1)

    def test_real_process_crash_after_provider_side_effect_reconciles_first(self):
        c=self.setup_controller('timeout_after_success')
        wid,a=self.approval()
        op=c.grant_approval(wid,a['approval_id'])
        code='''
import os,sys
from datetime import datetime
from app.workflow import WorkflowController
from app.provider_mock import ProviderMock
p=ProviderMock(sys.argv[1],user_id='alice',clock=lambda:datetime.fromisoformat(sys.argv[3]))
original=p.book
def crash(*args):
    try: original(*args)
    finally: os._exit(23)
p.book=crash
c=WorkflowController(sys.argv[1],user_id='alice',clock=p.clock,provider=p)
c.execute(sys.argv[2])
'''
        run=subprocess.run([sys.executable,'-X','utf8','-c',code,str(self.path),op,NOW.isoformat()],capture_output=True)
        self.assertEqual(run.returncode,23,run.stderr)
        self.assertEqual(len(self.rows('provider_bookings')),1)
        self.p.calls.clear()
        fresh=WorkflowController(self.path,user_id='alice',clock=self.clock,provider=self.p)
        r=fresh.recover()[0]
        self.assertEqual(r['status'],'BOOKED')
        self.assertEqual(self.p.calls[0]['tool'],'get_booking_status')
        self.assertNotIn('book',[v['tool'] for v in self.p.calls])
        self.assertEqual(len(self.rows('provider_bookings')),1)

    def test_slot_taken_and_provider_hold_expired_require_new_approval(self):
        for branch in ['slot_taken','hold_expired']:
            with self.subTest(branch=branch):
                if self.c is not None:
                    self.path=Path(self.tmp.name)/(branch+'.sqlite3')
                c=self.setup_controller(branch)
                wid,a=self.approval()
                r=c.confirm(wid,a['approval_id'])
                self.assertEqual(r['status'],'NEEDS_REAPPROVAL')
                self.assertFalse(self.rows('provider_bookings'))
                option=c.search(wid)[0]
                new=c.prepare_booking(wid,option['id'],option['free_slots'][1])
                self.assertNotEqual(new['approval_id'],a['approval_id'])
                self.deny('approval_invalid',lambda:c.confirm(wid,a['approval_id']))

    def test_cancel_503_same_key_verified_and_duplicate_safe(self):
        c=self.setup_controller()
        wid,b=self.booked()
        a=c.prepare_change(wid,'cancel',b['booking_id'])
        self.assertEqual(a['snapshot']['price_status'],'original_booking_price')
        self.assertEqual(a['snapshot']['price_amount'],900)
        r=c.confirm(wid,a['approval_id'])
        self.assertEqual(r['status'],'CANCELLED')
        calls=[v for v in self.p.calls if v['tool']=='cancel']
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]['args'][1],calls[1]['args'][1])
        self.assertEqual(self.rows('provider_bookings')[0]['status'],'cancelled')
        self.assertEqual(c.confirm(wid,a['approval_id'])['status'],'CANCELLED')

    def test_cancel_restart_after_503_reuses_key_and_verifies(self):
        c=self.setup_controller()
        wid,b=self.booked()
        a=c.prepare_change(wid,'cancel',b['booking_id'])
        op=c.grant_approval(wid,a['approval_id'])
        code='''
import os,sys
from datetime import datetime
from app.workflow import WorkflowController
from app.provider_mock import ProviderMock
p=ProviderMock(sys.argv[1],user_id='alice',clock=lambda:datetime.fromisoformat(sys.argv[3]))
original=p.cancel
def crash(*args):
    try: original(*args)
    finally: os._exit(23)
p.cancel=crash
WorkflowController(sys.argv[1],user_id='alice',clock=p.clock,provider=p).execute(sys.argv[2])
'''
        run=subprocess.run([sys.executable,'-X','utf8','-c',code,str(self.path),op,NOW.isoformat()],capture_output=True)
        self.assertEqual(run.returncode,23,run.stderr)
        fresh=WorkflowController(self.path,user_id='alice',clock=self.clock)
        self.assertEqual(fresh.execute(op)['status'],'CANCELLED')
        self.assertEqual(self.rows('provider_bookings')[0]['status'],'cancelled')
        self.assertEqual(len([v for v in self.rows('provider_operation_outcomes') if v['action']=='cancel']),1)

    def test_reschedule_conflict_preserves_original_and_fresh_success_verified(self):
        target='2026-11-02T11:00:00+05:30'
        c=self.setup_controller(conflicts=(target,))
        wid,b=self.booked()
        original=self.rows('provider_bookings')[0]['slot']
        a=c.prepare_change(wid,'reschedule',b['booking_id'],new_slot=target)
        self.assertEqual(a['snapshot']['new_price_status'],'unavailable_no_fee_mock')
        self.assertEqual(c.confirm(wid,a['approval_id'])['status'],'CONFLICT')
        self.assertEqual(self.rows('provider_bookings')[0]['slot'],original)
        new='2026-11-02T15:00:00+05:30'
        a2=c.prepare_change(wid,'reschedule',b['booking_id'],new_slot=new)
        self.assertEqual(c.confirm(wid,a2['approval_id'])['status'],'RESCHEDULED')
        self.assertEqual(self.rows('provider_bookings')[0]['slot'],new)

    def test_unknown_historical_price_disclosed_and_price_change_blocked(self):
        c=self.setup_controller()
        # Seed history using provider infrastructure; no controller price ledger.
        pid='plumber-0-0'; slot='2026-11-02T09:00:00+05:30'
        h=self.p.hold_slot(pid,slot)
        bid=self.p.book(h['hold_id'],'historical-book')['booking_id']
        wid=self.request()
        self.deny('price_unknown',lambda:c.prepare_change(wid,'reschedule',bid,
            new_slot='2026-11-02T11:00:00+05:30',price_change_requested=True))
        a=c.prepare_change(wid,'cancel',bid)
        self.assertIsNone(a['snapshot']['price_amount'])
        self.assertEqual(a['snapshot']['price_status'],'price_unavailable_from_provider_contract')
        self.assertEqual(c.confirm(wid,a['approval_id'])['status'],'CANCELLED')

    def test_price_changing_reschedule_blocked_even_with_original_quote(self):
        c=self.setup_controller()
        wid,b=self.booked()
        self.deny('price_unknown',lambda:c.prepare_change(wid,'reschedule',b['booking_id'],
            new_slot='2026-11-02T11:00:00+05:30',price_change_requested=True))
        self.assertEqual(self.rows('provider_bookings')[0]['slot'],'2026-11-02T09:00:00+05:30')

    def test_unexpected_provider_error_never_fabricates_success(self):
        c=self.setup_controller()
        wid,a=self.approval()
        self.p.fault=lambda name,args: (_ for _ in ()).throw(RuntimeError('synthetic unexpected')) if name=='book' else None
        r=c.confirm(wid,a['approval_id'])
        self.assertEqual(r['status'],'OUTCOME_UNKNOWN')
        self.assertIn('unverified',r['message'].lower())
        self.assertFalse(self.rows('provider_bookings'))

    def test_status_read_failure_after_commit_reports_unverified_then_recovers(self):
        c=self.setup_controller()
        wid,a=self.approval()
        count=[0]
        def fault(name,args):
            if name=='get_booking_status':
                count[0]+=1
                if count[0]>1: raise RuntimeError('status unavailable')
        self.p.fault=fault
        r=c.confirm(wid,a['approval_id'])
        self.assertEqual(r['status'],'OUTCOME_UNKNOWN')
        self.assertEqual(len(self.rows('provider_bookings')),1)
        self.p.fault=None
        self.assertEqual(c.execute(r['operation_id'])['status'],'BOOKED')
        self.assertEqual(len(self.rows('provider_bookings')),1)

    def test_constraints_earliest_hour_and_time_window_enforced(self):
        c=self.setup_controller()
        wid=self.request(preferences={'earliest_hour':10,'latest_hour':12,'technician':'Tech 0-0'})
        options=c.search(wid)
        self.assertTrue(options)
        self.assertEqual(len(options),1)
        self.assertTrue(all(datetime.fromisoformat(s).hour==11 for s in options[0]['free_slots']))
        self.deny('constraint_violation',lambda:c.prepare_booking(wid,'plumber-0-0','2026-11-02T09:00:00+05:30'))
        self.deny('constraint_violation',lambda:c.prepare_booking(wid,'plumber-0-1','2026-11-02T11:00:00+05:30'))

    def test_second_user_cannot_change_booking_even_with_known_id(self):
        c=self.setup_controller()
        wid,b=self.booked()
        other=WorkflowController(self.path,user_id='bob',clock=self.clock)
        own=other.create_request('bob-action')['workflow_id']
        self.deny('forbidden',lambda:other.prepare_change(own,'cancel',b['booking_id']))
        self.assertEqual(self.rows('provider_bookings')[0]['status'],'booked')

    def test_two_users_race_for_same_slot_one_approved_booking(self):
        c=self.setup_controller()
        wid=self.request()
        other=WorkflowController(self.path,user_id='bob',clock=self.clock)
        bw=other.create_request('bob',service='plumber',area='Indiranagar',date_window=WINDOW)['workflow_id']
        barrier=Barrier(2)
        def run(pair):
            controller,workflow=pair
            barrier.wait()
            try:
                a=controller.prepare_booking(workflow,'plumber-0-0','2026-11-02T09:00:00+05:30')
                return controller.confirm(workflow,a['approval_id'])['status']
            except ProviderError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(run,[(c,wid),(other,bw)]))
        self.assertEqual(sorted(outcomes),['BOOKED','slot_unavailable'])
        self.assertEqual(len(self.rows('provider_bookings')),1)

    def test_cancel_requires_its_own_approval_not_old_book_confirmation(self):
        c=self.setup_controller()
        wid,b=self.booked()
        book_op=b['operation_id']
        cancel=c.prepare_change(wid,'cancel',b['booking_id'])
        self.assertEqual(c.execute(book_op)['status'],'BOOKED')
        self.assertEqual(self.rows('provider_bookings')[0]['status'],'booked')
        c.confirm(wid,cancel['approval_id'])
        self.assertEqual(c.execute(book_op)['status'],'NOT_ACTIVE')
        self.assertEqual(self.rows('provider_bookings')[0]['status'],'cancelled')

    def test_response_success_without_authoritative_booking_never_claims_success(self):
        c=self.setup_controller()
        wid,a=self.approval()
        self.p.inner.book=lambda *args:{'booking_id':'fabricated-response'}
        result=c.confirm(wid,a['approval_id'])
        self.assertEqual(result['status'],'OUTCOME_UNKNOWN')
        self.assertFalse(self.rows('provider_bookings'))

    def test_provider_booked_different_slot_is_not_approved_success(self):
        c=self.setup_controller()
        wid,a=self.approval()
        original=self.p.inner.book
        def wrong_slot(*args):
            response=original(*args)
            self.p.inner.reschedule(response['booking_id'],'2026-11-02T11:00:00+05:30','test-only-external-move')
            return response
        self.p.inner.book=wrong_slot
        result=c.confirm(wid,a['approval_id'])
        self.assertEqual(result['status'],'OUTCOME_UNKNOWN')
        self.assertEqual(self.rows('provider_bookings')[0]['slot'],'2026-11-02T11:00:00+05:30')
        self.assertEqual(len(self.rows('provider_bookings')),1)

    def test_hold_expiring_during_status_read_stops_with_truthful_response(self):
        c=self.setup_controller('timeout_without_booking')
        wid,a=self.approval()
        calls=[0]
        def move_clock(name,args):
            if name=='get_booking_status':
                calls[0]+=1
                if calls[0]==2: self.clock.value=NOW+timedelta(minutes=10)
        self.p.fault=move_clock
        result=c.confirm(wid,a['approval_id'])
        self.assertEqual(result['status'],'OUTCOME_UNKNOWN')
        self.assertFalse(self.rows('provider_bookings'))
        self.assertEqual(len([x for x in self.p.calls if x['tool']=='book']),1)

if __name__=='__main__':
    unittest.main()
