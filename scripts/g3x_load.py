"""Measured 1 vs 100 active logical workflows, separately 100 confirmations of one.

Run on fresh isolated Compose projects for comparable zero-booking initial state.
These measurements are not a claim of 100x sustained throughput or G4 acceptance.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from threading import Barrier,Event,Thread
import time
import uuid
import psycopg
from psycopg.rows import dict_row

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests_g3x.test_distributed import Distributed
from app.runtime.pg import dsn
from app.runtime.provider_client import ProviderClient

def query(sql,args=()):
    with psycopg.connect(**dsn('orange_grader'),row_factory=dict_row) as db:return db.execute(sql,args).fetchall()
def percentiles(values):
    values=sorted(values)
    return {'p50_ms':values[int((len(values)-1)*.5)],'p95_ms':values[int((len(values)-1)*.95)],'max_ms':values[-1]} if values else {}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--count',type=int,choices=[1,100],required=True)
    parser.add_argument('--label',required=True);parser.add_argument('--base',default='http://gateway:8080');args=parser.parse_args()
    out=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'receipts'/args.label;out.mkdir(parents=True,exist_ok=False)
    initial={'workflows':query('SELECT count(*) n FROM authority.workflows')[0]['n'],
             'provider_bookings':query('SELECT count(*) n FROM provider.provider_bookings')[0]['n']}
    assert initial=={'workflows':0,'provider_bookings':0},'fresh isolated initial state required'
    trials=[];plans=[];http_metrics=[]
    now=datetime.now(timezone.utc);window={'start':now.isoformat(),'end':(now+timedelta(days=8)).isoformat()}
    seed_client=ProviderClient('load-fixture-reader');fixtures={}
    for service in ['plumber','electrician','ac servicing']:
        for area in ['Indiranagar','Koramangala']:
            fixtures[service,area]=seed_client.search_providers(service,area,window)
    branches=['book_success']*28+['slot_taken']*6+['timeout_after_success']*3+['timeout_without_booking']*3
    for i in range(args.count):
        trial=Distributed('test_http_duplicate_confirmation_two_replicas_one_operation');trial.setUp()
        branch='hold_expired' if i%25==24 else branches[i%40]
        trial.fault(book_branch=branch,quote_delta=250 if i%11==0 else 0,scenario_id='load-'+str(i),seed=20261101)
        service=['plumber','electrician','ac servicing'][i%3];area=['Indiranagar','Koramangala'][(i//3)%2]
        provider_index=(i//6)%3;slot_index=i//18
        if i%10==9:service='plumber';area='Indiranagar';provider_index=0;slot_index=0
        candidate=fixtures[service,area][provider_index]
        draft={'service':service,'area':area,'date_window':window,'budget_inr':2000}
        plans.append({'draft':draft,'provider_id':candidate['id'],'slot':candidate['free_slots'][slot_index],
                      'scenario':branch,'logical_id':'measured-'+str(i)})
        original=trial.call
        def measured(method,path,value=None,_call=original,**kw):
            start=time.monotonic()
            result=_call(method,path,value,base=args.base,**kw)
            http_metrics.append({'method':method,'route':path.split('/')[1],'latency_ms':(time.monotonic()-start)*1000,'http_status':result[0]})
            return result
        trial.call=measured;trials.append(trial)
    barrier=Barrier(args.count);started=time.monotonic();rows=[]
    def create(i):
        barrier.wait();code,result=trials[i].call('POST','/workflows',{'logical_request_id':plans[i]['logical_id'],'draft':plans[i]['draft']})
        return {'http_status':code,'result':result}
    with ThreadPoolExecutor(args.count) as pool:created=list(pool.map(create,range(args.count)))
    (out/'create_results.json').write_text(json.dumps(created,indent=2))
    (out/'create_state.json').write_text(json.dumps({'workflows':query('SELECT status,count(*) n FROM authority.workflows GROUP BY status'),
                                                   'provider_bookings':query('SELECT count(*) n FROM provider.provider_bookings')},indent=2))
    assert all(r['http_status']==200 for r in created),{code:sum(r['http_status']==code for r in created) for code in {r['http_status'] for r in created}}
    workflows=[r['result']['workflow_id'] for r in created]
    active=query("SELECT count(*) n FROM authority.workflows WHERE status='COLLECTING'")[0]['n']
    stop=Event();queue_samples=[]
    def sample():
        while not stop.is_set():
            counts=query('SELECT state,count(*) n FROM authority.jobs GROUP BY state')
            queue_samples.append({'elapsed_seconds':time.monotonic()-started,'counts':counts})
            stop.wait(.25)
    thread=Thread(target=sample);thread.start()
    def journey(i):
        trial=trials[i];plan=plans[i];wid=workflows[i];op=None
        if args.count==100 and i%10==0:
            foreign=workflows[(i+1)%args.count]
            assert trial.call('GET','/workflows/'+foreign)[0]==403
            assert trial.call('POST','/workflows/'+foreign+'/search',{})[0]==403
        code,_=trial.call('POST','/workflows/'+wid+'/search',{})
        code,a=trial.call('POST','/workflows/'+wid+'/hold',{'provider_id':plan['provider_id'],'slot':plan['slot']})
        if code!=200:return {'scenario':str(i),'expected':'faults remain safe; success only if verified','actual':a.get('error','UNAVAILABLE'),'operation_id':None,'latency_ms':(time.monotonic()-started)*1000}
        _,card=trial.call('GET','/approvals/'+a['approval_id'])
        code,pending=trial.call('POST','/approvals/'+a['approval_id']+'/confirm',card)
        if code!=200:return {'scenario':str(i),'expected':'approval remains exact','actual':pending.get('error','DENIED'),'operation_id':None,'latency_ms':(time.monotonic()-started)*1000}
        op=pending['operation_id'];deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            _,result=trial.call('GET','/operations/'+op)
            if result.get('status')!='PENDING_VERIFICATION':break
            time.sleep(.2)
        return {'scenario':str(i),'expected':'verified or truthful conflict/unknown','actual':result.get('status'),'operation_id':op,
                'trace_id':pending.get('trace_id'),'customer_result':result,'latency_ms':(time.monotonic()-started)*1000}
    try:
        with ThreadPoolExecutor(min(6,args.count)) as pool:rows=list(pool.map(journey,range(args.count)))
    finally:stop.set();thread.join(timeout=2)
    elapsed=time.monotonic()-started
    duplicate_result=None
    if args.count==100:
        trial=Distributed('test_http_duplicate_confirmation_two_replicas_one_operation');trial.setUp()
        trial.call=lambda method,path,value=None,_call=trial.call,**kw:_call(method,path,value,base=args.base,**kw)
        wid,a=trial.prepare();_,card=trial.call('GET','/approvals/'+a['approval_id'])
        duplicates=Barrier(100)
        def confirm(_):
            duplicates.wait();start=time.monotonic()
            code,result=trial.call('POST','/approvals/'+a['approval_id']+'/confirm',card)
            return {'http_status':code,'operation_id':result.get('operation_id'),'latency_ms':(time.monotonic()-start)*1000}
        with ThreadPoolExecutor(100) as pool:confirmations=list(pool.map(confirm,range(100)))
        operations={r['operation_id'] for r in confirmations if r['operation_id']}
        assert len(operations)==1,confirmations
        final=trial.poll(next(iter(operations)),seconds=25)
        count=query('SELECT count(*) n FROM provider.provider_bookings WHERE hold_id=%s',(a['snapshot']['hold_id'],))[0]['n']
        assert count<=1 and all(r['http_status']==200 for r in confirmations),confirmations
        duplicate_result={'requests':100,'distinct_operations':1,'bookings':count,'coalesced_confirmations':99,
                          'final_status':final['status'],'latency':percentiles([r['latency_ms'] for r in confirmations])}
        (out/'duplicate_confirmations.json').write_text(json.dumps(confirmations,indent=2))
    duplicate_slots=query("SELECT provider_id,slot,count(*) n FROM provider.provider_bookings WHERE status='booked' GROUP BY provider_id,slot HAVING count(*)>1")
    duplicate_intents=query('SELECT h.workflow_id,count(DISTINCT b.id) n FROM authority.workflow_holds h '
        'JOIN provider.provider_bookings b ON h.hold_id=b.hold_id GROUP BY h.workflow_id HAVING count(DISTINCT b.id)>1')
    missing_approval=query("SELECT b.id FROM provider.provider_bookings b JOIN authority.workflow_holds h ON h.hold_id=b.hold_id "
        "WHERE NOT EXISTS(SELECT 1 FROM authority.operations o JOIN authority.approval_snapshots a USING(approval_id) "
        "WHERE o.workflow_id=h.workflow_id AND o.action='book' AND a.status='GRANTED' AND o.user_id=b.user_id "
        "AND (o.snapshot_json::jsonb->>'hold_id')=b.hold_id AND o.payload_fingerprint=a.payload_fingerprint)")
    assert not duplicate_slots and not duplicate_intents and not missing_approval
    # Grader independently compares approved fields, provider rows and customer success.
    mismatched_approval=query("SELECT b.id FROM provider.provider_bookings b JOIN authority.workflow_holds h ON h.hold_id=b.hold_id "
        "JOIN authority.operations o ON o.workflow_id=h.workflow_id AND o.action='book' "
        "WHERE b.provider_id<>(o.snapshot_json::jsonb->>'provider_id') OR b.slot<>(o.snapshot_json::jsonb->>'new_slot') "
        "OR (o.snapshot_json::jsonb->>'price_amount')::numeric<>h.quoted_price")
    assert not mismatched_approval,mismatched_approval
    for row in rows:
        if row['actual']=='BOOKED':
            truth=query('SELECT b.* FROM provider.provider_bookings b JOIN authority.operations o '
                        "ON (o.snapshot_json::jsonb->>'hold_id')=b.hold_id WHERE o.operation_id=%s",(row['operation_id'],))
            assert len(truth)==1 and truth[0]['status']=='booked'
            assert row['customer_result']['booking_id']==truth[0]['id']
            assert row['customer_result']['booking']['slot']==truth[0]['slot']
    state={}
    for schema,table in [('authority',t) for t in ['workflows','approval_snapshots','operations','jobs']]+[('provider','provider_bookings'),('provider','provider_operation_outcomes')]:
        state[schema+'.'+table]=query('SELECT * FROM '+schema+'.'+table)
    (out/'independent_sql.json').write_text(json.dumps(state,default=str,indent=2))
    workers={r['worker'].split('-')[0] for r in state['authority.jobs'] if r['worker']}
    queues=[(r['claimed_at']-r['created_at']).total_seconds()*1000 for r in state['authority.jobs'] if r.get('claimed_at')]
    report={'seed':20261101,'initial_state':initial,'logical_workflows':args.count,'simultaneously_persisted_active_workflows':active,
        'elapsed_seconds':elapsed,'completed_workflows_per_second':len(rows)/elapsed,'http_latency':percentiles([r['latency_ms'] for r in http_metrics]),
        'journey_latency':percentiles([r['latency_ms'] for r in rows]),'queue_wait':percentiles(queues),
        'outcomes':{s:sum(r['actual']==s for r in rows) for s in {r['actual'] for r in rows}},
        'distinct_worker_processes_observed':len(workers),'duplicate_confirmation_experiment':duplicate_result,
        'persisted_mutation_attempts':sum(r['attempts'] for r in state['authority.operations']),
        'retries':sum(max(0,r['attempts']-1) for r in state['authority.operations']),
        'unknown_operations':sum(r['status']=='OUTCOME_UNKNOWN' for r in state['authority.operations']),
        'approval_payload_mismatches':mismatched_approval,
        'cross_user_read_write_attacks_rejected':20 if args.count==100 else 0,
        'provider_slot_violations':duplicate_slots,'logical_intent_violations':duplicate_intents,'approval_violations':missing_approval,
        'claims_boundary':'100x workload/concurrency factor; not 100x throughput, production HA or G4 agent evaluations.'}
    assert active==args.count
    if args.count==100:assert len(workers)>=2,workers
    (out/'results.json').write_text(json.dumps(report,default=str,indent=2))
    (out/'http_metrics.json').write_text(json.dumps(http_metrics,indent=2))
    (out/'queue_samples.json').write_text(json.dumps(queue_samples,default=str,indent=2))
    (out/'customer_results.json').write_text(json.dumps(rows,indent=2))
    actor_hashes={hashlib.sha256(trial.uid.encode()).hexdigest() for trial in trials}
    traces=out/'traces';traces.mkdir()
    for path in (Path(os.getenv('RUNTIME_STATE','data/runtime'))/'traces').glob('*.jsonl'):
        if any(json.loads(line).get('user_id_hash') in actor_hashes for line in path.read_text().splitlines()):
            (traces/path.name).write_bytes(path.read_bytes())
    with (out/'results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['scenario','expected','actual','operation_id','latency_ms'],extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(json.dumps(report,default=str,indent=2))

if __name__=='__main__':main()
