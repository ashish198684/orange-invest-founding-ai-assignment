"""Versioned, reversible local bootstrap. Admin role is never an API/worker role."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import psycopg
from app.storage import SCHEMA as PROVIDER_SCHEMA
from app.workflow import SCHEMA as WORKFLOW_SCHEMA
from app.runtime.pg import dsn

EXTRA='''
CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY, installed_at TIMESTAMPTZ DEFAULT now());
INSERT INTO schema_versions(version) VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(session_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(user_id),
 csrf_hash TEXT NOT NULL,expires_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS issued_cards(card_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,session_hash TEXT NOT NULL,
 approval_id TEXT NOT NULL REFERENCES approval_snapshots(approval_id),fingerprint TEXT NOT NULL,revision INTEGER NOT NULL,
 expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(operation_id TEXT PRIMARY KEY REFERENCES operations(operation_id),user_id TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'READY',generation INTEGER NOT NULL DEFAULT 0,claims INTEGER NOT NULL DEFAULT 0,
 worker TEXT,lease_until TIMESTAMPTZ,available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),initiation_deadline TIMESTAMPTZ NOT NULL DEFAULT now()+interval '20 seconds',
 recovery_deadline TIMESTAMPTZ NOT NULL DEFAULT now()+interval '5 minutes',traceparent TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS claim_ready ON jobs(available_at,created_at) WHERE state IN ('READY','LEASED');
CREATE TABLE IF NOT EXISTS memory_facts(fact_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,key TEXT NOT NULL,
 value_json TEXT,provenance TEXT NOT NULL CHECK(provenance IN ('user_stated','inferred')),confirmed BOOLEAN NOT NULL,
 version INTEGER NOT NULL,forgotten BOOLEAN NOT NULL DEFAULT false,source_event_hash TEXT NOT NULL,UNIQUE(user_id,key));
CREATE TABLE IF NOT EXISTS trace_events(event_id BIGSERIAL PRIMARY KEY,user_id TEXT NOT NULL,run_id TEXT NOT NULL,
 trace_id TEXT NOT NULL,event_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory_events(user_id TEXT NOT NULL,key TEXT NOT NULL,event_hash TEXT NOT NULL,
 kind TEXT NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(user_id,key,event_hash));
CREATE INDEX IF NOT EXISTS user_trace ON trace_events(user_id,run_id,event_id);
CREATE OR REPLACE FUNCTION immutable_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='approval_snapshots' THEN
  IF (to_jsonb(NEW)-'status'-'approved_at') IS DISTINCT FROM (to_jsonb(OLD)-'status'-'approved_at')
  THEN RAISE EXCEPTION 'immutable approval'; END IF;
 ELSE
  IF (to_jsonb(NEW)-'status'-'attempts'-'last_error'-'result_json'-'verified_at') IS DISTINCT FROM
     (to_jsonb(OLD)-'status'-'attempts'-'last_error'-'result_json'-'verified_at')
  THEN RAISE EXCEPTION 'immutable operation'; END IF;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS immutable_approval ON approval_snapshots;
CREATE TRIGGER immutable_approval BEFORE UPDATE ON approval_snapshots FOR EACH ROW EXECUTE FUNCTION immutable_snapshot();
DROP TRIGGER IF EXISTS immutable_operation ON operations;
CREATE TRIGGER immutable_operation BEFORE UPDATE ON operations FOR EACH ROW EXECUTE FUNCTION immutable_snapshot();
CREATE OR REPLACE FUNCTION enqueue_job(oid TEXT, uid TEXT, parent TEXT) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path=authority,pg_temp AS $$
BEGIN
 IF uid IS DISTINCT FROM current_setting('app.user_id',true) OR NOT EXISTS
 (SELECT 1 FROM operations WHERE operation_id=oid AND user_id=uid) THEN RAISE EXCEPTION 'forbidden'; END IF;
 PERFORM pg_advisory_xact_lock(77001);
 IF (SELECT count(*) FROM jobs WHERE state IN ('READY','LEASED'))>=512 OR
 (SELECT count(*) FROM jobs WHERE user_id=uid AND state IN ('READY','LEASED'))>=128
 THEN RAISE EXCEPTION 'queue_capacity'; END IF;
 INSERT INTO jobs(operation_id,user_id,traceparent) VALUES(oid,uid,parent);
END $$;
CREATE OR REPLACE FUNCTION claim_job(owner TEXT, target TEXT DEFAULT NULL) RETURNS SETOF jobs
LANGUAGE sql SECURITY DEFINER SET search_path=authority,pg_temp AS $$
 UPDATE jobs SET state='LEASED',worker=owner,generation=generation+1,claims=claims+1,
 lease_until=clock_timestamp()+interval '10 seconds'
 WHERE operation_id=(SELECT operation_id FROM jobs
 WHERE (target IS NULL OR operation_id=target) AND claims<6 AND recovery_deadline>clock_timestamp()
 AND ((state='READY' AND (available_at<=clock_timestamp() OR target IS NOT NULL)) OR
      (state='LEASED' AND lease_until<=clock_timestamp()))
 ORDER BY claims,created_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *;
$$;
REVOKE ALL ON FUNCTION enqueue_job(TEXT,TEXT,TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION claim_job(TEXT,TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION enqueue_job(TEXT,TEXT,TEXT) TO orange_app;
GRANT EXECUTE ON FUNCTION claim_job(TEXT,TEXT) TO orange_worker;
'''

def migrate(database=None):
    with psycopg.connect(**dsn('postgres',database),autocommit=True) as db:
        for role,password in [('orange_app','local-app-only'),('orange_provider','local-provider-only'),
                              ('orange_worker','local-worker-only'),('orange_grader','local-grader-only')]:
            exists=db.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
            if not exists: db.execute(psycopg.sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(psycopg.sql.Identifier(role),psycopg.sql.Literal(password)))
        db.execute('CREATE SCHEMA IF NOT EXISTS authority')
        db.execute('CREATE SCHEMA IF NOT EXISTS provider')
        db.execute('SET search_path=authority,public')
        db.execute(WORKFLOW_SCHEMA.split('CREATE TRIGGER')[0])
        db.execute(EXTRA)
        for table in ['workflows','approval_snapshots','operations','issued_cards','jobs','memory_facts','memory_events','trace_events']:
            db.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            db.execute(f'DROP POLICY IF EXISTS user_scope ON {table}')
            db.execute(f"CREATE POLICY user_scope ON {table} USING(user_id=current_setting('app.user_id',true)) WITH CHECK(user_id=current_setting('app.user_id',true))")
        db.execute('ALTER TABLE workflow_holds ENABLE ROW LEVEL SECURITY')
        db.execute('DROP POLICY IF EXISTS user_scope ON workflow_holds')
        db.execute("CREATE POLICY user_scope ON workflow_holds USING (EXISTS(SELECT 1 FROM workflows w WHERE w.workflow_id=workflow_holds.workflow_id))")
        db.execute('GRANT USAGE ON SCHEMA authority TO orange_app,orange_worker,orange_grader')
        db.execute('GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA authority TO orange_app')
        db.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA authority TO orange_app')
        db.execute('GRANT SELECT ON ALL TABLES IN SCHEMA authority TO orange_grader')
        # Independent read-only grader can see all synthetic principals, never mutate.
        for table in ['workflows','workflow_holds','approval_snapshots','operations','issued_cards','jobs','memory_facts','memory_events','trace_events']:
            db.execute(f'DROP POLICY IF EXISTS grade_all ON {table}')
            db.execute(f'CREATE POLICY grade_all ON {table} FOR SELECT TO orange_grader USING(true)')
        for name in ['alice','bob']:
            salt=hashlib.sha256(('synthetic-salt-'+name).encode()).hexdigest()
            hashed=hashlib.scrypt(('demo-'+name).encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
            db.execute('INSERT INTO users VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(name,salt,hashed))
        db.execute('SET search_path=provider,public')
        db.execute(PROVIDER_SCHEMA)
        db.execute('CREATE TABLE IF NOT EXISTS fault_settings(user_id TEXT PRIMARY KEY,config_json TEXT NOT NULL)')
        db.execute('GRANT USAGE ON SCHEMA provider TO orange_provider,orange_grader')
        db.execute('GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA provider TO orange_provider')
        db.execute('GRANT SELECT ON ALL TABLES IN SCHEMA provider TO orange_grader')
    state=Path(os.getenv('RUNTIME_STATE','data/runtime'))
    state.mkdir(parents=True,exist_ok=True)
    target=state/'runtime.json'
    if not target.exists():
        target.write_text(json.dumps({'session_secret':secrets.token_hex(32),'provider_secret':secrets.token_hex(32)}))
        target.chmod(0o600)
    print(json.dumps({'migration':1,'authority_schema':'authority','independent_provider_schema':'provider','status':'applied'}))

if __name__=='__main__': migrate()
