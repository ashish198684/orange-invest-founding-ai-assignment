"""Replayable G2 evidence probe, not the deferred G3 application tracing subsystem."""
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.provider_mock import ProviderMock,ScenarioConfig
from app.workflow import WorkflowController

def main(target):
    out=Path(target)
    out.mkdir(exist_ok=False,parents=True)
    path=out/'controller_timeout.sqlite3'
    clock=lambda:datetime.fromisoformat('2026-11-01T09:00:00+05:30')
    events=[]
    def event(kind,**values):
        events.append({'sequence':len(events)+1,'evidence_kind':'G2_local_synthetic_probe','event':kind,**values})
    class ObservedProvider:
        def __init__(self,inner): self.inner=inner
        def __getattr__(self,name):
            method=getattr(self.inner,name)
            if not callable(method) or name.startswith('_'): return method
            def call(*args):
                event('tool_call',tool=name,args=args)
                try:
                    result=method(*args)
                    event('tool_result',tool=name,result=result)
                    return result
                except Exception as exc:
                    event('tool_error',tool=name,error=type(exc).__name__)
                    raise
            return call
    provider=ObservedProvider(ProviderMock(path,user_id='g2-synthetic',clock=clock,
                  config=ScenarioConfig(book_branch='timeout_after_success',quote_delta=200)))
    c=WorkflowController(path,user_id='g2-synthetic',clock=clock,provider=provider)
    w=c.create_request('one-logical-request',service='plumber',area='Indiranagar',budget_inr=1500,
                       date_window={'start':clock().isoformat(),'end':'2026-11-09T00:00:00+05:30'})
    wid=w['workflow_id']
    choice=c.search(wid)[0]
    approval=c.prepare_booking(wid,choice['id'],choice['free_slots'][0])
    event('approval_shown',approval=approval)
    op=c.grant_approval(wid,approval['approval_id'])
    event('approval_granted_operation_persisted',operation_id=op)
    result=c.execute(op)
    event('customer_result',result=result)
    assert result['status']=='BOOKED'
    restarted=WorkflowController(path,user_id='g2-synthetic',clock=clock)
    replay=restarted.confirm(wid,approval['approval_id'])
    event('controller_restart_duplicate_confirmation',result=replay)
    assert replay['booking_id']==result['booking_id']
    with provider.store.connect() as db:
        tables=['workflows','approval_snapshots','operations','workflow_holds','provider_holds',
                'provider_bookings','provider_operation_outcomes']
        snapshot={name:[dict(r) for r in db.execute('SELECT * FROM '+name)] for name in tables}
        assert len(snapshot['provider_bookings'])==1
        assert len(snapshot['operations'])==1
        assert snapshot['operations'][0]['payload_fingerprint']==approval['fingerprint']
        assert snapshot['provider_operation_outcomes'][0]['error_code']=='timeout_after_success'
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    event('independent_database_observation',snapshot=snapshot,integrity_check=integrity)
    (out/'events.jsonl').write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in events),encoding='utf-8')
    (out/'database.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
    (out/'customer_result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'verified_result':result,'booking_count':1,'integrity_check':integrity},indent=2))

if __name__=='__main__':
    main(sys.argv[1])
