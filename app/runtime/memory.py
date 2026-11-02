"""Fresh database retrieval only; versioned correction and value-erasing tombstones."""
import hashlib
import json
import uuid
from app.runtime.pg import PgStore
from app.runtime.observe import active

class Memory:
    def __init__(self,user_id):self.user_id=user_id;self.store=PgStore(user_id)
    def view(self):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM memory_facts WHERE user_id=?',(self.user_id,))]
    def context(self):
        # No process cache or audit-history fallback is permitted.
        return {r['key']:json.loads(r['value_json']) for r in self.view()
                if not r['forgotten'] and r['confirmed'] and r['value_json'] is not None}
    def update(self,key,value,*,event_id,expected_version=0,provenance='user_stated',forget=False,confirm=False):
        if key not in {'area','earliest_hour','technician'}:raise ValueError('invalid_memory_key')
        if provenance not in {'user_stated','inferred'}:raise ValueError('invalid_provenance')
        event_hash=hashlib.sha256(event_id.encode()).hexdigest()
        with self.store.connect(write=True) as db:
            if db.execute('SELECT 1 FROM memory_events WHERE user_id=? AND key=? AND event_hash=?',
                          (self.user_id,key,event_hash)).fetchone():raise ValueError('stale_memory_event')
            old=db.execute('SELECT * FROM memory_facts WHERE user_id=? AND key=?',(self.user_id,key)).fetchone()
            version=old['version'] if old else 0
            if version!=expected_version:raise ValueError('stale_memory_version')
            if confirm:
                if not old or old['forgotten']:raise ValueError('forgotten_memory')
                value=json.loads(old['value_json']);provenance=old['provenance']
            raw=None if forget else json.dumps(value)
            db.execute('INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET '
                       'value_json=excluded.value_json,provenance=excluded.provenance,confirmed=excluded.confirmed,'
                       'version=excluded.version,forgotten=excluded.forgotten,source_event_hash=excluded.source_event_hash',
                       (uuid.uuid4().hex,self.user_id,key,raw,provenance,not forget and (provenance=='user_stated' or confirm),
                        version+1,forget,event_hash))
            db.execute('INSERT INTO memory_events VALUES(?,?,?,?,?)',(self.user_id,key,event_hash,'forget' if forget else 'confirm' if confirm else 'write',version+1))
        run=active.get()
        if run:run.emit('memory_action',action='forget' if forget else 'confirm' if confirm else 'write',memory_key_hash=hashlib.sha256(key.encode()).hexdigest())
        return {'version':version+1,'forgotten':forget}
