"""Actual PostgreSQL, HTTP replicas and process-failure conformance scenarios."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import urllib.request
import urllib.error
import uuid
import psycopg
from psycopg.rows import dict_row
from app.runtime.pg import PgStore,dsn,LostLease
from app.runtime.controller import PgController
from app.runtime.provider_client import ProviderClient
from app.runtime.memory import Memory
from app.runtime.observe import Run,scope,BudgetExceeded
from app.runtime.worker import claim,perform
from app.provider_mock import ProviderError,ProviderTimeout
from app.workflow import SafetyError

ORIGIN='http://127.0.0.1:8080'
class Distributed(unittest.TestCase):
    def setUp(self):
        self.uid='trial-'+uuid.uuid4().hex[:12];self.events=[];self.cookie='';self.csrf='';self.extra_evidence={}
        salt=hashlib.sha256(self.uid.encode()).hexdigest()
        password=hashlib.scrypt(b'synthetic-test',salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        with psycopg.connect(**dsn('postgres')) as db:
            db.execute('INSERT INTO authority.users VALUES(%s,%s,%s)',(self.uid,salt,password))
        self.fault(book_branch='book_success')
        self.call('POST','/login',{'username':self.uid,'password':'synthetic-test'})
        self.c=PgController(self.uid)
    def fault(self,**values):
        with psycopg.connect(**dsn('postgres')) as db:
            db.execute('INSERT INTO provider.fault_settings VALUES(%s,%s) ON CONFLICT(user_id) DO UPDATE SET config_json=excluded.config_json',
                       (self.uid,json.dumps(values)))
    def call(self,method,path,value=None,*,base='http://api:8080',csrf=True,cookie=None):
        headers={'Content-Type':'application/json','Origin':ORIGIN,'Cookie':self.cookie if cookie is None else cookie}
        if csrf:headers['X-CSRF-Token']=self.csrf
        request=urllib.request.Request(base+path,data=json.dumps(value).encode() if value is not None else None,headers=headers,method=method)
        try:response=urllib.request.urlopen(request,timeout=21)
        except urllib.error.HTTPError as exc:response=exc
        data=json.load(response)
        if path=='/login' and response.code==200:
            self.cookie=response.headers['Set-Cookie'].split(';')[0];self.csrf=data['csrf_token']
        self.events.append({'method':method,'path':path,'status_code':response.code,
                            'result_status':data.get('status') if isinstance(data,dict) else 'list'})
        return response.code,data
    def draft(self):
        now=datetime.now(timezone.utc)
        bucket=int(hashlib.sha256(self._testMethodName.encode()).hexdigest()[:4],16)%6
        return {'service':['plumber','electrician','ac servicing'][bucket%3],
                'area':['Indiranagar','Koramangala'][bucket//3],'budget_inr':2000,
                'date_window':{'start':now.isoformat(),'end':(now+timedelta(days=8)).isoformat()}}
    def prepare(self,*,reserved=False):
        w=self.c.create_request(uuid.uuid4().hex,**self.draft())['workflow_id']
        p=next(p for p in self.c.search(w) if p['free_slots'])
        a=self.c.prepare_booking(w,p['id'],p['free_slots'][0])
        if reserved:
            original=self.c.store.enqueue
            def enqueue(db,oid):
                original(db,oid)
                db.execute("UPDATE jobs SET available_at=clock_timestamp()+interval '1 hour' WHERE operation_id=?",(oid,))
            self.c.store.enqueue=enqueue
        return w,a
    def reserve(self):
        w,a=self.prepare(reserved=True)
        return w,a,self.c.grant_approval(w,a['approval_id'])
    def poll(self,oid,seconds=18):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            _,r=self.call('GET','/operations/'+oid)
            if r.get('status')!='PENDING_VERIFICATION':return r
            time.sleep(.15)
        self.fail('operation did not reach a truthful bounded response')
    def sql(self,query,args=()):
        with psycopg.connect(**dsn('orange_grader'),row_factory=dict_row) as db:return db.execute(query,args).fetchall()
    def tearDown(self):
        target=os.getenv('G3X_EVIDENCE_DIR')
        if target:
            out=Path(target)/self._testMethodName;out.mkdir(parents=True,exist_ok=False)
            tables={}
            for schema,table in [('authority',t) for t in ['workflows','approval_snapshots','operations','jobs','memory_facts','trace_events']]+[
                ('provider',t) for t in ['provider_holds','provider_bookings','provider_operation_outcomes']]:
                tables[schema+'.'+table]=self.sql('SELECT * FROM '+schema+'.'+table+' WHERE user_id=%s',(self.uid,))
            (out/'sql_state.json').write_text(json.dumps(tables,default=str,indent=2)+'\n')
            (out/'http_observations.json').write_text(json.dumps(self.events,indent=2)+'\n')
            (out/'correlation.json').write_text(json.dumps({'actor_hash':hashlib.sha256(self.uid.encode()).hexdigest(),**self.extra_evidence},indent=2)+'\n')

    def test_http_card_issuance_csrf_session_and_no_alternate_mutation(self):
        w,a=self.prepare()
        self.assertEqual(self.call('POST','/approvals/'+a['approval_id']+'/confirm',{})[0],403)
        _,card=self.call('GET','/approvals/'+a['approval_id'])
        self.assertEqual(card['snapshot'],a['snapshot'])
        forged=json.loads(json.dumps(card));forged['snapshot']['price_amount']=1
        self.assertEqual(self.call('POST','/approvals/'+a['approval_id']+'/confirm',forged)[0],403)
        self.assertEqual(self.call('POST','/approvals/'+a['approval_id']+'/confirm',card,csrf=False)[0],403)
        self.assertEqual(self.call('POST','/operations/forged/execute',{})[0],400)
        _,r=self.call('POST','/approvals/'+a['approval_id']+'/confirm',card,base='http://api2:8080')
        self.assertEqual(r['status'],'PENDING_VERIFICATION')
        self.assertEqual(self.poll(r['operation_id'])['status'],'BOOKED')

    def test_http_duplicate_confirmation_two_replicas_one_operation(self):
        w,a=self.prepare();_,card=self.call('GET','/approvals/'+a['approval_id'])
        def confirm(base):return self.call('POST','/approvals/'+a['approval_id']+'/confirm',card,base=base)[1]
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(confirm,['http://api:8080','http://api2:8080']))
        self.assertEqual(results[0]['operation_id'],results[1]['operation_id'])
        self.assertEqual(self.poll(results[0]['operation_id'])['status'],'BOOKED')
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,))),1)

    def test_stale_card_revision_aba_and_identity_override_rejected(self):
        w,a=self.prepare();_,card=self.call('GET','/approvals/'+a['approval_id'])
        self.c.correct(w,area='Koramangala');self.c.correct(w,area='Indiranagar')
        self.assertEqual(self.call('POST','/approvals/'+a['approval_id']+'/confirm',card)[0],409)
        self.assertEqual(self.call('POST','/workflows',{'user_id':'bob','logical_request_id':'spoof'})[0],403)
        self.assertEqual(self.call('GET','/workflows/'+w,cookie=self.cookie+'forged')[0],403)
        other,_=__import__('app.runtime.security',fromlist=['login']).login('bob','demo-bob')
        self.assertEqual(self.call('GET','/workflows/'+w,cookie='orange_session='+other)[0],403)

    def test_exact_quote_budget_and_no_model_approval(self):
        self.fault(book_branch='book_success',quote_delta=300)
        w,a=self.prepare()
        self.assertEqual(a['snapshot']['price_amount'],self.c.provider.get_provider(a['snapshot']['provider_id'])['price']+300)
        with self.assertRaises(SafetyError):self.c.propose(w,{'approved':True})
        with self.assertRaises(SafetyError):self.c.chat(w,'yes')
        self.c.correct(w,budget_inr=900)
        option=self.c.search(w)[0]
        with self.assertRaises(SafetyError):self.c.prepare_booking(w,option['id'],option['free_slots'][1])
        self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))

    def test_provider_commit_survives_rolled_back_authority_transaction(self):
        p=ProviderClient(self.uid)
        option=next(p for p in p.search_providers('plumber','Indiranagar',self.draft()['date_window']) if p['free_slots'])
        hold=p.hold_slot(option['id'],option['free_slots'][0]);key='boundary-'+uuid.uuid4().hex
        with self.assertRaises(RuntimeError):
            with PgStore(self.uid).connect(write=True) as db:
                db.execute('INSERT INTO trace_events(user_id,run_id,trace_id,event_json) VALUES(?,?,?,?)',(self.uid,'rollback','0','{}'))
                p.book(hold['hold_id'],key)
                raise RuntimeError('rollback authority only')
        self.assertEqual(p.get_booking_status(key)['status'],'booked')
        self.assertFalse(self.sql("SELECT * FROM authority.trace_events WHERE user_id=%s AND run_id='rollback'",(self.uid,)))

    def test_timeout_after_success_and_logical_request_deduplication(self):
        self.fault(book_branch='timeout_after_success')
        w,a,oid=self.reserve();job=claim(oid)
        result=perform(job)
        self.assertEqual(result['status'],'BOOKED')
        with self.assertRaises(SafetyError):self.c.prepare_booking(w,'plumber-0-1',a['snapshot']['new_slot'])
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,))),1)
        self.assertEqual(PgController(self.uid).execute(oid)['booking_id'],result['booking_id'])

    def test_timeout_without_booking_three_attempts_no_new_key(self):
        self.fault(book_branch='timeout_without_booking')
        w,a,oid=self.reserve();result=perform(claim(oid))
        self.assertEqual(result['status'],'OUTCOME_UNKNOWN')
        op=self.sql('SELECT * FROM authority.operations WHERE operation_id=%s',(oid,))[0]
        self.assertEqual(op['attempts'],3)
        self.assertEqual(PgController(self.uid).execute(oid)['status'],'OUTCOME_UNKNOWN')
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_operation_outcomes WHERE user_id=%s',(self.uid,))),1)
        self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))

    def test_provider_slot_taken_and_hold_expired_conformance(self):
        for branch in ['slot_taken','hold_expired']:
            self.fault(book_branch=branch)
            w,a,oid=self.reserve();result=perform(claim(oid))
            self.assertEqual(result['status'],'NEEDS_REAPPROVAL')
            self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))

    def test_provider_process_dies_after_commit_restarted_workers_reconcile(self):
        self.fault(book_branch='book_success',terminate_after_method='book')
        w,a=self.prepare();oid=self.c.grant_approval(w,a['approval_id'])
        deadline=time.monotonic()+25;observed=[]
        while time.monotonic()<deadline:
            _,result=self.call('GET','/operations/'+oid);observed.append(result.get('status'))
            if result.get('status')=='BOOKED':break
            time.sleep(.25)
        self.assertEqual(result.get('status'),'BOOKED',observed)
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))),1)

    def test_response_loss_after_provider_commit_does_not_repeat_effect(self):
        self.fault(book_branch='book_success',response_loss_method='book',delay=25)
        w,a,oid=self.reserve();result=perform(claim(oid))
        self.assertEqual(result['status'],'BOOKED')
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))),1)

    def test_cancel_retry_and_reschedule_conflict_preserve_truth(self):
        w,a,oid=self.reserve();book=perform(claim(oid));bid=book['booking_id']
        draft=self.draft()
        options=ProviderClient(self.uid).search_providers(draft['service'],draft['area'],draft['date_window'])
        target=next(p for p in options if p['id']==a['snapshot']['provider_id'])['free_slots'][0]
        self.fault(book_branch='book_success',reschedule_conflicts=[target])
        change=self.c.prepare_change(w,'reschedule',bid,new_slot=target)
        move=self.c.grant_approval(w,change['approval_id']);result=perform(claim(move))
        self.assertEqual(result['status'],'CONFLICT')
        self.assertEqual(ProviderClient(self.uid).list_bookings(self.uid)[0]['slot'],a['snapshot']['new_slot'])
        self.fault(book_branch='book_success')
        change=self.c.prepare_change(w,'reschedule',bid,new_slot=target)
        move=self.c.grant_approval(w,change['approval_id']);self.assertEqual(perform(claim(move))['status'],'RESCHEDULED')
        change=self.c.prepare_change(w,'cancel',bid);cancel=self.c.grant_approval(w,change['approval_id'])
        self.assertEqual(perform(claim(cancel))['status'],'CANCELLED')
        outcomes=self.sql("SELECT * FROM provider.provider_operation_outcomes WHERE user_id=%s AND action='cancel'",(self.uid,))
        self.assertEqual(outcomes[0]['attempts'],2)

    def test_crash_before_and_after_provider_and_status_recovery(self):
        for fault in ['before_provider','after_provider','status_readback']:
            w,a,oid=self.reserve()
            process=subprocess.run([sys.executable,'-m','app.runtime.worker','--once','--job',oid,'--fault',fault],capture_output=True,timeout=15)
            self.assertIn(process.returncode,[31,32,34])
            with psycopg.connect(**dsn('postgres')) as db:
                db.execute("UPDATE authority.jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE operation_id=%s",(oid,))
            replacement=claim(oid)
            if replacement:perform(replacement)
            self.assertEqual(self.poll(oid)['status'],'BOOKED')
            self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))),1)

    def test_expired_worker_cannot_update_state(self):
        w,a,oid=self.reserve();old=claim(oid)
        with psycopg.connect(**dsn('postgres')) as db:
            db.execute("UPDATE authority.jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE operation_id=%s",(oid,))
        replacement=claim(oid);self.assertIsNotNone(replacement)
        self.assertEqual(perform(replacement)['status'],'BOOKED')
        stale=PgController(self.uid,fence=(oid,old['generation']))
        with self.assertRaises(LostLease):stale.execute(oid)
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,))),1)

    def test_memory_cross_replica_forget_stale_replay_and_privacy(self):
        a=Memory(self.uid);b=Memory(self.uid);secret='forget-marker-'+uuid.uuid4().hex
        a.update('area',secret,event_id='stated')
        stale=b.context();self.assertEqual(stale['area'],secret)
        a.update('area','corrected',event_id='correct',expected_version=1)
        a.update('area',None,event_id='forget',expected_version=2,forget=True)
        self.assertEqual(b.context(),{})
        with self.assertRaises(ValueError):b.update('area',secret,event_id='stated',expected_version=3)
        self.assertIsNone(a.view()[0]['value_json'])
        self.assertNotIn(secret,json.dumps(self.sql('SELECT * FROM authority.trace_events WHERE user_id=%s',(self.uid,))))
        self.assertEqual(Memory('bob').context(),{})

    def test_model_context_drops_forgotten_memory_without_persisting_it_in_draft(self):
        m=Memory(self.uid);m.update('area','Indiranagar',event_id='known')
        w=self.c.create_request('memory-context',service='plumber')['workflow_id']
        self.assertEqual(self.c.view(w)['draft']['area'],'Indiranagar')
        m.update('area',None,event_id='forget',expected_version=1,forget=True)
        self.assertNotIn('area',PgController(self.uid).view(w)['draft'])
        self.assertEqual(self.c.next_question(w)['field'],'area')

    def test_blocked_model_is_killed_before_wall_deadline(self):
        from app.runtime.model import IsolatedModel
        run=Run(self.uid,wall=.3);started=time.monotonic()
        with scope(run,'blocked-model'):
            with self.assertRaises(BudgetExceeded):IsolatedModel(delay=25).interpret('plumber',datetime.now(timezone.utc))
        self.assertLess(time.monotonic()-started,2)

    def test_inferred_memory_not_applied_until_confirmed(self):
        m=Memory(self.uid);m.update('earliest_hour',10,event_id='inference',provenance='inferred')
        self.assertEqual(m.context(),{})
        m.update('earliest_hour',None,event_id='confirm',expected_version=1,confirm=True)
        self.assertEqual(m.context(),{'earliest_hour':10})

    def test_actual_tool_model_and_wall_caps(self):
        run=Run(self.uid,wall=.3)
        with scope(run,'budget-test'):
            for _ in range(8):run.charge('model')
            with self.assertRaises(BudgetExceeded):run.charge('model')
        run=Run(self.uid)
        with scope(run,'tool-cap'):
            for _ in range(16):ProviderClient(self.uid).get_provider('plumber-0-0')
            with self.assertRaises(BudgetExceeded):ProviderClient(self.uid).get_provider('plumber-0-0')
            self.assertEqual(run.tools,16)
        self.fault(book_branch='book_success',hang_method='get_provider',delay=25)
        run=Run(self.uid,wall=.4);started=time.monotonic()
        with scope(run,'hung-call'):
            with self.assertRaises(ProviderTimeout):ProviderClient(self.uid).get_provider('plumber-0-0')
        self.assertLess(time.monotonic()-started,2)

    def test_model_turn_cap_at_actual_interpreter_boundary(self):
        from app.runtime.model import IsolatedModel
        run=Run(self.uid)
        with scope(run,'actual-model-cap'):
            for _ in range(8):self.assertEqual(IsolatedModel().interpret('plumber',datetime.now(timezone.utc)),{'service':'plumber'})
            with self.assertRaises(BudgetExceeded):IsolatedModel().interpret('plumber',datetime.now(timezone.utc))
            self.assertEqual(run.models,8)

    def test_real_zombie_worker_after_committed_provider_cannot_overwrite_replacement(self):
        w,a,oid=self.reserve()
        child=subprocess.Popen([sys.executable,'-m','app.runtime.worker','--once','--job',oid,'--fault','zombie'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        deadline=time.monotonic()+7
        while time.monotonic()<deadline:
            if self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],)):break
            time.sleep(.1)
        self.assertTrue(self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],)))
        with psycopg.connect(**dsn('postgres')) as db:
            db.execute("UPDATE authority.jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE operation_id=%s",(oid,))
        replacement=claim(oid)
        if replacement:perform(replacement)
        _,err=child.communicate(timeout=18)
        self.assertEqual(child.returncode,0,err.decode())
        self.assertEqual(self.poll(oid)['status'],'BOOKED')
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))),1)

    def test_http_hung_provider_returns_within_20_seconds_without_booking(self):
        w=self.c.create_request('hung-http',**self.draft())['workflow_id']
        self.fault(book_branch='book_success',hang_method='get_provider',delay=25)
        started=time.monotonic()
        code,result=self.call('POST','/workflows/'+w+'/hold',{'provider_id':'plumber-0-0','slot':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
        self.assertLess(time.monotonic()-started,20)
        self.assertEqual(code,409)
        self.assertNotEqual(result.get('status'),'BOOKED')
        self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))

    def test_local_otel_context_propagates_api_queue_worker_provider(self):
        import base64
        w,a=self.prepare();_,card=self.call('GET','/approvals/'+a['approval_id'])
        _,pending=self.call('POST','/approvals/'+a['approval_id']+'/confirm',card)
        self.assertEqual(self.poll(pending['operation_id'])['status'],'BOOKED')
        time.sleep(.3)
        trace_id=pending['trace_id'];names=[]
        for line in (Path(os.getenv('RUNTIME_STATE','data/runtime'))/'otel.jsonl').read_text().splitlines():
            for resource in json.loads(line).get('resourceSpans',[]):
                for library in resource.get('scopeSpans',[]):
                    for span in library.get('spans',[]):
                        if base64.b64decode(span['traceId']).hex()==trace_id:names.append(span['name'])
        for required in ['api.POST.approvals','worker.execute','provider.book','provider.server.book']:
            self.assertIn(required,names)
        other,_=__import__('app.runtime.security',fromlist=['login']).login('bob','demo-bob')
        self.assertEqual(self.call('GET','/traces/'+pending['run_id'],cookie='orange_session='+other)[0],403)

    def test_issued_card_expiry_session_expiry_and_cross_user_operations(self):
        w,a,oid=self.reserve()
        with psycopg.connect(**dsn('postgres')) as db:
            db.execute('UPDATE authority.sessions SET expires_at=now()-interval \'1 second\' WHERE user_id=%s',(self.uid,))
        self.assertEqual(self.call('GET','/operations/'+oid)[0],403)
        with self.assertRaises(SafetyError):PgController('bob').execute(oid)
        self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))

    def test_untrusted_reviews_do_not_modify_intent_or_permissions(self):
        w,a=self.prepare();before=self.c.view(w)
        draft=self.draft()
        pid=ProviderClient(self.uid).search_providers(draft['service'],draft['area'],draft['date_window'])[0]['id']
        reviews=self.c.details(pid)['reviews']
        self.assertTrue(any('SYSTEM' in r['text'] for r in reviews))
        self.assertTrue(all(r['trust']=='untrusted' for r in reviews))
        self.assertEqual(self.c.view(w),before)
        self.assertFalse(self.sql('SELECT * FROM authority.operations WHERE user_id=%s',(self.uid,)))

    def test_unknown_price_change_fails_closed(self):
        w,a,oid=self.reserve();result=perform(claim(oid))
        with self.assertRaises(SafetyError):self.c.prepare_change(w,'reschedule',result['booking_id'],
            new_slot=a['snapshot']['new_slot'],price_change_requested=True)

    def test_expired_initiating_turn_cannot_start_first_booking_effect(self):
        w,a,oid=self.reserve()
        with psycopg.connect(**dsn('postgres')) as db:
            db.execute("UPDATE authority.jobs SET initiation_deadline=now()-interval '1 second' WHERE operation_id=%s",(oid,))
        result=perform(claim(oid))
        self.assertEqual(result['status'],'NEEDS_REAPPROVAL')
        self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))

    def test_poison_claim_bound_enters_unknown_deadletter(self):
        w,a,oid=self.reserve()
        with psycopg.connect(**dsn('postgres')) as db:
            db.execute('UPDATE authority.jobs SET claims=6 WHERE operation_id=%s',(oid,))
        self.assertIsNone(claim(oid))
        row=self.sql('SELECT * FROM authority.jobs WHERE operation_id=%s',(oid,))[0]
        self.assertEqual(row['state'],'DEAD')
        self.assertEqual(self.poll(oid)['status'],'OUTCOME_UNKNOWN')
        self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))

    def test_client_disconnect_replays_same_persisted_operation(self):
        import http.client
        w,a=self.prepare();_,card=self.call('GET','/approvals/'+a['approval_id'])
        connection=http.client.HTTPConnection('api',8080,timeout=2)
        connection.request('POST','/approvals/'+a['approval_id']+'/confirm',json.dumps(card),
            {'Content-Type':'application/json','Origin':ORIGIN,'Cookie':self.cookie,'X-CSRF-Token':self.csrf})
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            rows=self.sql('SELECT operation_id FROM authority.operations WHERE approval_id=%s',(a['approval_id'],))
            if rows:break
            time.sleep(.05)
        connection.close()  # the client intentionally never consumes the first response
        self.assertTrue(rows)
        _,replay=self.call('POST','/approvals/'+a['approval_id']+'/confirm',card,base='http://api2:8080')
        self.assertEqual(replay['operation_id'],rows[0]['operation_id'])
        self.assertEqual(self.poll(replay['operation_id'])['status'],'BOOKED')
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))),1)

    def test_expired_inference_cannot_be_confirmed_or_retrieved(self):
        memory=Memory(self.uid)
        memory.update('area','Indiranagar',event_id='inferred',provenance='inferred')
        row=self.sql('SELECT * FROM authority.memory_facts WHERE user_id=%s',(self.uid,))[0]
        self.assertIsNotNone(row['expires_at'])
        with self.c.store.connect(write=True) as db:
            db.execute("UPDATE memory_facts SET expires_at=clock_timestamp()-interval '1 second' WHERE user_id=?",(self.uid,))
        self.assertEqual(memory.context(),{})
        self.assertIsNone(memory.view()[0]['value_json'])
        with self.assertRaises(ValueError):memory.update('area',None,event_id='late-confirm',expected_version=1,confirm=True)

    def test_concurrent_views_use_one_database_slot_each(self):
        from threading import Barrier
        w=self.c.create_request('pool-regression',**self.draft())['workflow_id']
        original=Memory.view;barrier=Barrier(12)
        def synchronized(memory,db=None):
            if db is not None:barrier.wait(timeout=5)
            return original(memory,db)
        Memory.view=synchronized
        try:
            with ThreadPoolExecutor(12) as pool:rows=list(pool.map(lambda _:self.c.view(w),range(12)))
        finally:Memory.view=original
        self.assertEqual(len(rows),12)
        self.assertTrue(all(row['workflow_id']==w for row in rows))

    def test_wrong_slot_readback_cannot_claim_success(self):
        w,a,oid=self.reserve();original=self.c.provider.list_bookings
        def wrong_slot(uid):
            rows=original(uid)
            return [{**row,'slot':'2099-01-01T10:00:00+05:30'} for row in rows]
        self.c.provider.list_bookings=wrong_slot
        self.assertEqual(self.c.execute(oid)['status'],'OUTCOME_UNKNOWN')
        truth=self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))
        self.assertEqual(len(truth),1);self.assertEqual(truth[0]['slot'],a['snapshot']['new_slot'])
        self.assertEqual(PgController(self.uid).execute(oid)['status'],'BOOKED')
        self.assertEqual(len(self.sql('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))),1)

    def test_status_unavailable_prevents_mutation_until_reconciled(self):
        w,a,oid=self.reserve()
        def unavailable(key):raise ProviderError('transient_503',503)
        self.c.provider.get_booking_status=unavailable
        self.assertEqual(self.c.execute(oid)['status'],'OUTCOME_UNKNOWN')
        self.assertFalse(self.sql('SELECT * FROM provider.provider_bookings WHERE user_id=%s',(self.uid,)))
        self.assertEqual(PgController(self.uid).execute(oid)['status'],'BOOKED')

    def test_memory_forget_during_inflight_search_discards_stale_context(self):
        memory=Memory(self.uid);memory.update('area','Indiranagar',event_id='remember')
        w=self.c.create_request('inflight-memory',service='plumber',date_window=self.draft()['date_window'])['workflow_id']
        original=self.c.provider.search_providers
        def forget_during_rpc(*args):
            memory.update('area',None,event_id='forget',expected_version=1,forget=True)
            return original(*args)
        self.c.provider.search_providers=forget_during_rpc
        with self.assertRaises(SafetyError):self.c.search(w)
        self.assertNotIn('area',self.c.view(w)['draft'])
        self.assertFalse(self.sql('SELECT * FROM authority.operations WHERE user_id=%s',(self.uid,)))

    def test_memory_forget_during_hold_cannot_publish_stale_approval(self):
        memory=Memory(self.uid);memory.update('area','Indiranagar',event_id='remember')
        w=self.c.create_request('inflight-hold',service='plumber',date_window=self.draft()['date_window'])['workflow_id']
        p=next(p for p in self.c.search(w) if p['free_slots'])
        original=self.c.provider.hold_slot
        def forget_during_rpc(*args):
            memory.update('area',None,event_id='forget',expected_version=1,forget=True)
            return original(*args)
        self.c.provider.hold_slot=forget_during_rpc
        with self.assertRaises(SafetyError):self.c.prepare_booking(w,p['id'],p['free_slots'][0])
        self.assertFalse(self.sql('SELECT * FROM authority.approval_snapshots WHERE user_id=%s',(self.uid,)))

    def test_memory_forget_across_actual_api_replicas_and_worker_context(self):
        self.assertEqual(self.call('POST','/memory',{'key':'area','value':'Indiranagar','event_id':'one'})[0],200)
        self.assertEqual(self.call('GET','/context',base='http://api2:8080')[1]['area'],'Indiranagar')
        self.assertEqual(self.call('POST','/memory',{'key':'area','value':None,'event_id':'forget','expected_version':1,'forget':True})[0],200)
        self.assertNotIn('area',self.call('GET','/context',base='http://api2:8080')[1])
        child=subprocess.run([sys.executable,'-c','import json,sys;from app.runtime.memory import Memory;print(json.dumps(Memory(sys.argv[1]).context()))',self.uid],capture_output=True,timeout=5)
        self.assertEqual(child.returncode,0)
        self.assertEqual(json.loads(child.stdout),{})

    def test_http_timeout_after_success_receipt(self):
        self.fault(book_branch='timeout_after_success')
        w,a=self.prepare();_,card=self.call('GET','/approvals/'+a['approval_id'])
        _,pending=self.call('POST','/approvals/'+a['approval_id']+'/confirm',card)
        result=self.poll(pending['operation_id'])
        self.assertEqual(result['status'],'BOOKED')
        self.assertEqual(result['booking']['slot'],a['snapshot']['new_slot'])
        actor=hashlib.sha256(self.uid.encode()).hexdigest();events=[]
        for path in (Path(os.environ.get('RUNTIME_STATE','data/runtime'))/'traces').glob('*.jsonl'):
            events.extend(row for row in map(json.loads,path.read_text().splitlines()) if row['user_id_hash']==actor)
        timeout=next(e for e in events if e['event_type']=='provider_timeout' and e['tool_name']=='book')
        self.assertEqual(timeout['error_class'],'ProviderTimeout');self.assertGreater(timeout['duration_ms'],0)
        self.assertEqual(len(timeout['idempotency_key_suffix_or_hash']),64)
        required={'timestamp','workflow_id','sanitized_args','sanitized_result','approval_fingerprint_prefix','decision_reason','exit_reason'}
        self.assertTrue(all(required<=event.keys() for event in events))
        self.extra_evidence={'trace_ids':[card['trace_id'],pending['trace_id']],
                             'approved_snapshot':a,'operation_id':pending['operation_id'],'customer_result':result}

    def test_trace_redacts_credentials_and_rejects_private_payloads(self):
        run=Run(self.uid)
        with scope(run,'redaction-test'):
            event=run.emit('run_exit',exit_reason='test',private_message='private-memory-sentinel',
                           decision_reason='Bearer synthetic-private-token',
                           sanitized_args={'password':'private-memory-sentinel','argument_count':1})
        raw=json.dumps(event)
        self.assertNotIn('synthetic-private-token',raw);self.assertNotIn('private-memory-sentinel',raw)
        self.assertEqual(event['sanitized_args'],{'argument_count':1})

if __name__=='__main__':unittest.main()
