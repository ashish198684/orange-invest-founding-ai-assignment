"""Narrow SQL compatibility adapter for the existing, tested business core."""
from contextlib import contextmanager
import hashlib
import os
import re
import psycopg
from psycopg.rows import dict_row

class LostLease(Exception): pass

def dsn(role='orange_app', database=None):
    passwords={'orange_app':'local-app-only','orange_provider':'local-provider-only',
               'orange_worker':'local-worker-only','orange_grader':'local-grader-only','postgres':'local-bootstrap-only'}
    return dict(host=os.getenv('PGHOST','pg'),dbname=database or os.getenv('PGDATABASE','orange'),
                user=role,password=passwords[role],connect_timeout=2)

class Row(dict):
    def __getitem__(self,key):
        return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

class Cursor:
    def __init__(self,cursor): self.cursor=cursor
    def fetchone(self):
        row=self.cursor.fetchone()
        return Row(row) if row is not None else None
    def fetchall(self): return [Row(r) for r in self.cursor.fetchall()]
    def __iter__(self): return iter(self.fetchall())
    @property
    def rowcount(self): return self.cursor.rowcount

class Connection:
    def __init__(self,db): self.db=db
    def execute(self,sql,args=()):
        sql=sql.replace('?', '%s').replace('ORDER BY rowid','ORDER BY operation_id')
        return Cursor(self.db.execute(sql,args))

class PgStore:
    managed_schema=True
    external_provider=True
    def __init__(self,user_id,*,role='orange_app',fence=None,database=None):
        self.principal=user_id
        self.role=role
        self.fence=fence
        self.database=database
        self.path='postgresql-independent-'+role

    @contextmanager
    def connect(self,*,write=False):
        schema='provider' if self.role=='orange_provider' else 'authority'
        with psycopg.connect(**dsn(self.role,self.database),row_factory=dict_row) as db:
            db.execute('SET LOCAL statement_timeout=2500')
            db.execute('SET LOCAL lock_timeout=2000')
            db.execute('SELECT set_config(%s,%s,true)',('search_path',schema+',public'))
            db.execute('SELECT set_config(%s,%s,true)',('app.user_id',self.principal))
            if write:
                # Short transaction coordination only. Never held across provider RPC.
                identity='provider-atomic-write' if schema=='provider' else self.principal
                key=int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8],'big',signed=True)
                db.execute('SELECT pg_advisory_xact_lock(%s)',(key,))
                if self.fence:
                    oid,generation=self.fence
                    found=db.execute("SELECT 1 FROM authority.jobs WHERE operation_id=%s AND generation=%s "
                        "AND lease_until>clock_timestamp() AND state='LEASED' FOR UPDATE",(oid,generation)).fetchone()
                    if not found: raise LostLease('stale worker fenced')
            yield Connection(db)

    def enqueue(self,db,operation_id):
        from app.runtime.observe import current_traceparent
        db.execute('SELECT authority.enqueue_job(?,?,?)',(operation_id,self.principal,current_traceparent()))
