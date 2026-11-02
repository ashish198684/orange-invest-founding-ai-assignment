"""Narrow SQL compatibility adapter for the existing, tested business core."""
from contextlib import contextmanager
import hashlib
import os
import re
from threading import BoundedSemaphore
from queue import Queue,Empty,Full
import psycopg
from psycopg.rows import dict_row

class LostLease(Exception): pass
_connections=BoundedSemaphore(12)
_idle={}

@contextmanager
def connection_slot():
    from app.runtime.observe import active
    run=active.get()
    if not _connections.acquire(timeout=min(5,run.remaining()) if run else 5):raise TimeoutError('connection_capacity')
    try:yield
    finally:_connections.release()

@contextmanager
def borrow(role,database=None):
    # A bounded reusable pool per process/role/database. Transaction-local user
    # and search_path settings are cleared by commit/rollback before reuse.
    pool=_idle.setdefault((role,database),Queue(maxsize=12))
    with connection_slot():
        try:db=pool.get_nowait()
        except Empty:db=psycopg.connect(**dsn(role,database),row_factory=dict_row)
        if db.closed:db=psycopg.connect(**dsn(role,database),row_factory=dict_row)
        try:
            with db.transaction():yield db
        finally:
            if not db.closed and db.info.transaction_status==psycopg.pq.TransactionStatus.IDLE:
                try:pool.put_nowait(db)
                except Full:db.close()
            else:db.close()

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
        with borrow(self.role,self.database) as db:
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
        from app.runtime.observe import current_traceparent,active
        db.execute('SELECT authority.enqueue_job(?,?,?)',(operation_id,self.principal,current_traceparent()))
        run=active.get()
        remaining=run.remaining() if run else 18.0
        db.execute("UPDATE jobs SET initiation_deadline=clock_timestamp()+make_interval(secs=>?) WHERE operation_id=?",
                   (remaining,operation_id))
