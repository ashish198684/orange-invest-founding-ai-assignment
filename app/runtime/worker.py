"""Fenced local outbox workers. Duplicate provider calls retain the same key."""
import argparse
import hashlib
import json
import os
import time
import uuid
import psycopg
from psycopg.rows import dict_row
from app.runtime.pg import dsn,PgStore,LostLease,borrow
from app.runtime.controller import PgController
from app.runtime.observe import Run,scope
from app.workflow import SafetyError

def claim(target=None):
    with borrow('orange_worker') as db:
        return db.execute('SELECT * FROM authority.claim_job(%s,%s)',(os.getenv('HOSTNAME','local')+'-'+uuid.uuid4().hex[:8],target)).fetchone()

def perform(job,fault=None):
    uid=job['user_id'];oid=job['operation_id'];generation=job['generation']
    run=Run(uid,wall=8)
    c=PgController(uid,fence=(oid,generation))
    with c.store.connect() as db:
        op=db.execute('SELECT workflow_id FROM operations WHERE operation_id=?',(oid,)).fetchone()
        run.workflow_id=op['workflow_id'] if op else None
    with scope(run,'worker.execute',job['traceparent']):
        run.emit('job_claim',operation_hash=hashlib.sha256(oid.encode()).hexdigest(),generation=generation)
        if fault=='before_provider':os._exit(31)
        if fault:
            original=c.provider._call
            def crashing(name,args):
                if fault=='status_readback' and name=='get_booking_status':os._exit(34)
                try:result=original(name,args)
                except Exception:
                    if fault=='after_503' and name=='cancel':os._exit(33)
                    if fault=='after_provider' and name=='book':os._exit(32)
                    raise
                if fault=='after_provider' and name in {'book','cancel','reschedule'}:os._exit(32)
                if fault=='zombie' and name=='book':time.sleep(12)
                return result
            c.provider._call=crashing
        try:
            result=c.execute(oid)
        except LostLease:
            run.emit('run_exit',exit_reason='stale_worker_fenced');return None
        except SafetyError as exc:
            if exc.code=='initiating_run_expired':
                with c.store.connect() as db:op,_,_=c._operation(db,oid)
                result=c._finish(op,'NEEDS_REAPPROVAL',reason=exc.code)
            else:raise
        except Exception:
            # Retain durable operation for bounded reclaim; no invented success.
            run.emit('run_exit',exit_reason='worker_error_pending_reconciliation');return None
        with c.store.connect(write=True) as db:
            op=db.execute('SELECT * FROM operations WHERE operation_id=?',(oid,)).fetchone()
            retry=(result['status']=='OUTCOME_UNKNOWN' and op['attempts']<3 and job['claims']<6)
            db.execute("UPDATE jobs SET state=?,available_at=clock_timestamp()+interval '1 second',lease_until=NULL,finished_at=clock_timestamp() "
                       "WHERE operation_id=? AND generation=?",('READY' if retry else 'DEAD' if result['status']=='OUTCOME_UNKNOWN' else 'DONE',oid,generation))
        run.emit('run_exit',status=result['status'],exit_reason='pending' if retry else result['status'])
        return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--once',action='store_true');p.add_argument('--job');p.add_argument('--fault')
    args=p.parse_args()
    while True:
        job=claim(args.job)
        if job:perform(job,args.fault)
        elif args.once:break
        if args.once:break
        time.sleep(.15 if not job else .01)

if __name__=='__main__':main()
