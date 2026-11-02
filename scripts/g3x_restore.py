"""Disposable synthetic restoration rehearsal; provider RPC remains on LIVE ledger."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid
import psycopg
from psycopg.rows import dict_row
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tests_g3x.test_distributed import Distributed
from app.runtime.pg import dsn
from app.runtime.controller import PgController
from app.runtime.provider_client import ProviderClient
from app.runtime.migrate import migrate

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--rollback',action='store_true');p.add_argument('--database');p.add_argument('--label',required=True);a=p.parse_args()
    out=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'receipts'/a.label
    if a.prepare:
        out.mkdir(exist_ok=False,parents=True)
        trial=Distributed('test_timeout_after_success_and_logical_request_deduplication');trial.setUp()
        w,approval,oid=trial.reserve()
        with trial.c.store.connect() as db:op=dict(db.execute('SELECT * FROM operations WHERE operation_id=?',(oid,)).fetchone())
        booked=ProviderClient(trial.uid).book(approval['snapshot']['hold_id'],op['idempotency_key'])
        fixture={'user_id':trial.uid,'workflow_id':w,'operation_id':oid,'hold_id':approval['snapshot']['hold_id'],
                 'idempotency_key':op['idempotency_key'],'booking_id':booked['booking_id'],
                 'authority_before_backup':'PREPARED','provider_before_backup':'booked'}
        (out/'fixture.json').write_text(json.dumps(fixture,indent=2))
        print(json.dumps(fixture,indent=2));return
    if not a.database or not a.database.startswith('orange_rehearsal_'):raise ValueError('only named disposable rehearsal databases allowed')
    if a.rollback:
        migrate(a.database)
        with psycopg.connect(**dsn('postgres',a.database),autocommit=True) as db:
            db.execute('DROP SCHEMA authority CASCADE; DROP SCHEMA provider CASCADE')
        migrate(a.database)
        with psycopg.connect(**dsn('orange_grader',a.database)) as db:
            assert db.execute('SELECT max(version) FROM authority.schema_versions').fetchone()[0]==3
            assert db.execute('SELECT count(*) FROM authority.operations').fetchone()[0]==0
        record={'database':a.database,'migration_versions_reapplied':[1,2,3],'empty_schema_rollback_rebuild':'PASS',
                'scope':'Disposable newly created database only. Never a destructive live downgrade.'}
        (out/'rollback_check.json').write_text(json.dumps(record,indent=2));print(json.dumps(record));return
    fixture=json.loads((out/'fixture.json').read_text())
    # Restored authority uses a separate DB; provider adapter intentionally stays on
    # the original independent service. Restoring our DB never rolls back that effect.
    c=PgController(fixture['user_id'],database=a.database)
    first=c.execute(fixture['operation_id']);second=c.execute(fixture['operation_id'])
    assert first['status']=='BOOKED' and first['booking_id']==second['booking_id']==fixture['booking_id']
    with psycopg.connect(**dsn('orange_grader'),row_factory=dict_row) as db:
        live=db.execute('SELECT * FROM provider.provider_bookings WHERE hold_id=%s',(fixture['hold_id'],)).fetchall()
    assert len(live)==1
    # Reapplying migrations with an old pending operation must preserve key/payload.
    migrate(a.database)
    with c.store.connect() as db:
        restored=dict(db.execute('SELECT * FROM operations WHERE operation_id=?',(fixture['operation_id'],)).fetchone())
        versions=[r[0] for r in db.execute('SELECT version FROM schema_versions ORDER BY version')]
    assert restored['idempotency_key']==fixture['idempotency_key']
    assert versions==[1,2,3]
    record={'restored_database':a.database,'first_readback':first,'duplicate_delivery':second,
            'live_provider_bookings':live,'restored_operation':restored,'migration_versions':versions,
            'provider_rollback_claim':False,'limitations':'Only a disposable synthetic snapshot was restored. Provider RPC remained on its independently committed live ledger. Old sensitive backups must be restricted and deletion suppressions reapplied before operational restoration.'}
    (out/'restore_verification.json').write_text(json.dumps(record,default=str,indent=2))
    print(json.dumps(record,default=str,indent=2))

if __name__=='__main__':main()
