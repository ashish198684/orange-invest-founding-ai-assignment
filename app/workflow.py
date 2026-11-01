"""Deterministic G2 authority. Provider records, never model text, establish truth.

The embedding server constructs this controller from trusted session identity.
approve/confirm is a separate explicit customer action; chat/proposals cannot call it.
SQLite transactions protect approval/intent records; an OS-released local DB lock
serializes provider reconciliation/execution across processes without a long DB tx.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import uuid

from app.agent.scripted import ScriptedModel
from app.provider_mock import ProviderMock, ProviderError
from app.provider_mock.fixtures import IST


class SafetyError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RequestContext:
    user_id: str


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def fingerprint(snapshot):
    return hashlib.sha256(encode(snapshot).encode()).hexdigest()


def timestamp(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.utcoffset() is None:
            raise ValueError('aware timestamp required')
        return dt.astimezone(IST)
    except (ValueError, TypeError):
        raise SafetyError('invalid_timestamp') from None


SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
 workflow_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, logical_request_id TEXT NOT NULL,
 initial_draft_json TEXT NOT NULL, draft_json TEXT NOT NULL, revision INTEGER NOT NULL,
 status TEXT NOT NULL, booking_id TEXT, current_approval_id TEXT, created_at TEXT NOT NULL,
 UNIQUE(user_id,logical_request_id)
);
CREATE TABLE IF NOT EXISTS workflow_holds (
 hold_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id),
 revision INTEGER NOT NULL, provider_id TEXT NOT NULL, slot TEXT NOT NULL,
 quoted_price INTEGER NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approval_snapshots (
 approval_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id),
 user_id TEXT NOT NULL, snapshot_json TEXT NOT NULL, payload_fingerprint TEXT NOT NULL,
 revision INTEGER NOT NULL, expires_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('PENDING','GRANTED','VOID')), approved_at TEXT
);
CREATE TABLE IF NOT EXISTS operations (
 operation_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id),
 user_id TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('book','cancel','reschedule')),
 booking_id TEXT, idempotency_key TEXT NOT NULL UNIQUE,
 approval_id TEXT NOT NULL UNIQUE REFERENCES approval_snapshots(approval_id),
 snapshot_json TEXT NOT NULL, payload_fingerprint TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('PREPARED','EXECUTING','OUTCOME_UNKNOWN','COMMITTED','FAILED')),
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
 last_error TEXT, result_json TEXT, verified_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS one_live_book_intent ON operations(workflow_id)
 WHERE action='book' AND status!='FAILED';
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_booking_change ON operations(booking_id)
 WHERE booking_id IS NOT NULL AND status IN ('PREPARED','EXECUTING','OUTCOME_UNKNOWN');
CREATE TRIGGER IF NOT EXISTS immutable_approval BEFORE UPDATE ON approval_snapshots
 WHEN NEW.approval_id IS NOT OLD.approval_id OR NEW.workflow_id IS NOT OLD.workflow_id
 OR NEW.user_id IS NOT OLD.user_id OR NEW.snapshot_json IS NOT OLD.snapshot_json
 OR NEW.payload_fingerprint IS NOT OLD.payload_fingerprint OR NEW.revision IS NOT OLD.revision
 OR NEW.expires_at IS NOT OLD.expires_at
 BEGIN SELECT RAISE(ABORT,'immutable approval'); END;
CREATE TRIGGER IF NOT EXISTS immutable_operation BEFORE UPDATE ON operations
 WHEN NEW.operation_id IS NOT OLD.operation_id OR NEW.workflow_id IS NOT OLD.workflow_id
 OR NEW.user_id IS NOT OLD.user_id OR NEW.action IS NOT OLD.action
 OR NEW.booking_id IS NOT OLD.booking_id OR NEW.idempotency_key IS NOT OLD.idempotency_key
 OR NEW.approval_id IS NOT OLD.approval_id OR NEW.snapshot_json IS NOT OLD.snapshot_json
 OR NEW.payload_fingerprint IS NOT OLD.payload_fingerprint
 BEGIN SELECT RAISE(ABORT,'immutable operation'); END;
"""

# Reduced G2 state graph, recorded in ADR-007. State changes use this guard.
EDITABLE = {'COLLECTING','CHOOSING','AWAITING_APPROVAL','NEEDS_REAPPROVAL','CONFLICT'}
ALLOWED = {
    'COLLECTING': {'CHOOSING','AWAITING_APPROVAL'},
    'CHOOSING': {'COLLECTING','AWAITING_APPROVAL'},
    'AWAITING_APPROVAL': {'COLLECTING','CHOOSING','EXECUTING','NEEDS_REAPPROVAL'},
    'EXECUTING': {'VERIFYING','BOOKED','CANCELLED','RESCHEDULED','OUTCOME_UNKNOWN','NEEDS_REAPPROVAL','CONFLICT'},
    'VERIFYING': {'EXECUTING','BOOKED','CANCELLED','RESCHEDULED','OUTCOME_UNKNOWN','NEEDS_REAPPROVAL','CONFLICT'},
    'OUTCOME_UNKNOWN': {'EXECUTING','VERIFYING','BOOKED','CANCELLED','RESCHEDULED','NEEDS_REAPPROVAL','CONFLICT'},
    'NEEDS_REAPPROVAL': {'COLLECTING','CHOOSING','AWAITING_APPROVAL'},
    'CONFLICT': {'COLLECTING','CHOOSING','AWAITING_APPROVAL'},
    'BOOKED': {'AWAITING_APPROVAL'},
    'RESCHEDULED': {'AWAITING_APPROVAL'},
    'CANCELLED': set(),
}


@contextmanager
def execution_lock(path):
    """Local coordination only. A killed process releases the kernel lock."""
    lock_path = Path(str(path)+'.controller.lock')
    with lock_path.open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        import os
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class WorkflowController:
    MAX_ATTEMPTS = 3  # one delivery + two same-key retries; durable across restart

    def __init__(self, db_path, *, user_id, clock=None, provider=None):
        if not isinstance(user_id,str) or not user_id.strip():
            raise SafetyError('forbidden')
        self.context = RequestContext(user_id)
        self.clock = clock or (lambda:datetime.now(IST))
        self.path = Path(db_path).resolve()
        self.provider = provider or ProviderMock(self.path,user_id=user_id,clock=self.clock)
        self._check_context()
        self.store = self.provider.store
        db = self.store._open()
        try:
            db.executescript(SCHEMA)
        finally:
            db.close()

    def _check_context(self):
        if (self.provider.user_id != self.context.user_id
                or Path(self.provider.store.path).resolve() != self.path):
            raise SafetyError('forbidden')

    def _now(self):
        now = self.clock()
        if now.utcoffset() is None:
            raise SafetyError('invalid_timestamp')
        return now.astimezone(IST)

    def _owned(self, db, wid):
        row = db.execute('SELECT * FROM workflows WHERE workflow_id=?',(wid,)).fetchone()
        if row is None or row['user_id'] != self.context.user_id:
            raise SafetyError('forbidden')
        return row

    def _state(self, db, wid, state):
        row = self._owned(db,wid)
        if state != row['status'] and state not in ALLOWED[row['status']]:
            raise SafetyError('illegal_transition')
        db.execute('UPDATE workflows SET status=? WHERE workflow_id=?',(state,wid))

    def _editable(self, db, w, *, booking=False):
        pending = db.execute("SELECT 1 FROM operations WHERE workflow_id=? AND status IN "
                             "('PREPARED','EXECUTING','OUTCOME_UNKNOWN')",(w['workflow_id'],)).fetchone()
        if pending or (booking and (w['booking_id'] or w['status'] not in EDITABLE)):
            raise SafetyError('request_locked')

    def _patch(self, fields):
        allowed = {'service','area','date_window','budget_inr','preferences','provider_id','slot'}
        if not isinstance(fields,dict) or set(fields)-allowed:
            raise SafetyError('untrusted_fields')
        fields = json.loads(encode(fields))  # detach input; only JSON values
        for key in ['service','area','provider_id']:
            if key in fields and (not isinstance(fields[key],str) or not fields[key].strip()):
                raise SafetyError('invalid_draft')
        if 'budget_inr' in fields and fields['budget_inr'] is not None:
            b=fields['budget_inr']
            if type(b) is not int or b<0:
                raise SafetyError('invalid_draft')
        if 'date_window' in fields:
            window=fields['date_window']
            if not isinstance(window,dict) or set(window)!={'start','end'}:
                raise SafetyError('invalid_draft')
            start,end=timestamp(window['start']),timestamp(window['end'])
            if end<=start: raise SafetyError('invalid_draft')
            fields['date_window']={'start':start.isoformat(),'end':end.isoformat()}
        if 'slot' in fields:
            fields['slot']=timestamp(fields['slot']).isoformat()
        if 'preferences' in fields:
            prefs=fields['preferences']
            if not isinstance(prefs,dict) or set(prefs)-{'earliest_hour','latest_hour','technician'}:
                raise SafetyError('invalid_draft')
            for k in ['earliest_hour','latest_hour']:
                if k in prefs and (type(prefs[k]) is not int or not 0<=prefs[k]<=24):
                    raise SafetyError('invalid_draft')
            if 'technician' in prefs and not isinstance(prefs['technician'],str):
                raise SafetyError('invalid_draft')
        return fields

    def create_request(self, logical_request_id, **fields):
        if not isinstance(logical_request_id,str) or not logical_request_id.strip():
            raise SafetyError('invalid_draft')
        fields=self._patch(fields)
        with self.store.connect(write=True) as db:
            old=db.execute('SELECT * FROM workflows WHERE user_id=? AND logical_request_id=?',
                           (self.context.user_id,logical_request_id)).fetchone()
            if old:
                if encode(fields)!=old['initial_draft_json']:
                    raise SafetyError('logical_request_mismatch')
                wid=old['workflow_id']
            else:
                wid=uuid.uuid4().hex
                db.execute('INSERT INTO workflows VALUES (?,?,?,?,?,?,?,NULL,NULL,?)',
                           (wid,self.context.user_id,logical_request_id,encode(fields),encode(fields),
                            0,'COLLECTING',self._now().isoformat()))
        return self.view(wid)

    def view(self, workflow_id):
        with self.store.connect() as db:
            w=self._owned(db,workflow_id)
            return {'workflow_id':w['workflow_id'],'logical_request_id':w['logical_request_id'],
                    'draft':json.loads(w['draft_json']),'revision':w['revision'],
                    'status':w['status'],'booking_id':w['booking_id']}

    def next_question(self, workflow_id):
        draft=self.view(workflow_id)['draft']
        for field in ['service','area','date_window']:
            if not draft.get(field):
                return {'field':field,'message':f'Please provide {field.replace("_"," ")}.'}
        return None  # budget/preferences are optional; never invent them

    def correct(self, workflow_id, **fields):
        fields=self._patch(fields)
        with self.store.connect(write=True) as db:
            w=self._owned(db,workflow_id)
            self._editable(db,w,booking=True)
            draft=json.loads(w['draft_json'])
            if 'preferences' in fields:
                fields['preferences']={**draft.get('preferences',{}),**fields['preferences']}
            draft.update(fields)
            db.execute("UPDATE approval_snapshots SET status='VOID' WHERE workflow_id=? AND status='PENDING'",(workflow_id,))
            db.execute('UPDATE workflows SET draft_json=?,revision=revision+1,current_approval_id=NULL WHERE workflow_id=?',
                       (encode(draft),workflow_id))
            self._state(db,workflow_id,'COLLECTING' if any(not draft.get(k) for k in ['service','area','date_window']) else 'CHOOSING')
        return self.view(workflow_id)

    def propose(self, workflow_id, proposal):
        return self.correct(workflow_id,**self._patch(proposal))

    def chat(self, workflow_id, text):
        if text.strip().lower() in {'yes','y','confirm','approved','approve','ok','okay'}:
            raise SafetyError('approval_required')
        patch=ScriptedModel().interpret(text,self._now())
        if patch: self.propose(workflow_id,patch)
        return {'workflow':self.view(workflow_id),'question':self.next_question(workflow_id),
                'message':'Constraints recorded. Consequential actions require an exact approval card.'}

    def details(self, provider_id):
        self._check_context()
        detail=self.provider.get_provider(provider_id)
        return {**detail,'reviews':[{'source':'provider_review','trust':'untrusted','text':r}
                                   for r in detail['reviews']]}

    def _matches(self, draft, detail, slot=None):
        if detail['service']!=draft.get('service') or detail['area']!=draft.get('area'):
            return False
        prefs=draft.get('preferences',{})
        if prefs.get('technician') and detail['attributes'].get('technician')!=prefs['technician']:
            return False
        if draft.get('provider_id') and detail['id']!=draft['provider_id']:
            return False
        if slot:
            dt=timestamp(slot)
            if not timestamp(draft['date_window']['start'])<=dt<timestamp(draft['date_window']['end']): return False
            if not prefs.get('earliest_hour',0)<=dt.hour<prefs.get('latest_hour',24): return False
        return True

    def search(self, workflow_id):
        self._check_context()
        w=self.view(workflow_id)
        if self.next_question(workflow_id): raise SafetyError('missing_fields')
        d=w['draft']
        rows=self.provider.search_providers(d['service'],d['area'],d['date_window'])
        results=[]
        for p in rows:
            detail={'id':p['id'],'service':p['attributes']['service'],'area':p['attributes']['area'],'attributes':p['attributes']}
            if not self._matches(d,detail): continue
            if d.get('budget_inr') is not None and p['price']>d['budget_inr']: continue
            results.append({**p,'free_slots':[s for s in p['free_slots'] if self._matches(d,detail,s)]})
        with self.store.connect(write=True) as db:
            current=self._owned(db,workflow_id)
            if current['status'] in {'COLLECTING','NEEDS_REAPPROVAL','CONFLICT'}:
                self._state(db,workflow_id,'CHOOSING')
        return results

    def _approval(self, db, w, snapshot):
        aid=uuid.uuid4().hex
        db.execute("UPDATE approval_snapshots SET status='VOID' WHERE workflow_id=? AND status='PENDING'",(w['workflow_id'],))
        db.execute('UPDATE workflows SET revision=?,current_approval_id=? WHERE workflow_id=?',
                   (snapshot['revision'],aid,w['workflow_id']))
        self._state(db,w['workflow_id'],'AWAITING_APPROVAL')
        db.execute('INSERT INTO approval_snapshots VALUES (?,?,?,?,?,?,?,?,NULL)',
                   (aid,w['workflow_id'],self.context.user_id,encode(snapshot),fingerprint(snapshot),
                    snapshot['revision'],snapshot['expires_at'],'PENDING'))
        return {'approval_id':aid,'snapshot':snapshot,'fingerprint':fingerprint(snapshot),'status':'PENDING'}

    def prepare_booking(self, workflow_id, provider_id, slot):
        self._check_context()
        slot=timestamp(slot).isoformat()
        with self.store.connect() as db:
            w=self._owned(db,workflow_id)
            self._editable(db,w,booking=True)
            revision=w['revision']
            draft=json.loads(w['draft_json'])
        if self.next_question(workflow_id): raise SafetyError('missing_fields')
        detail=self.provider.get_provider(provider_id)
        if not self._matches(draft,detail,slot): raise SafetyError('constraint_violation')
        hold=self.provider.hold_slot(provider_id,slot)
        if draft.get('budget_inr') is not None and hold['quoted_price']>draft['budget_inr']:
            raise SafetyError('budget_exceeded')
        with self.store.connect(write=True) as db:
            w=self._owned(db,workflow_id)
            self._editable(db,w,booking=True)
            if w['revision']!=revision: raise SafetyError('approval_invalid')
            revision+=1
            snapshot={'user_id':self.context.user_id,'workflow_id':workflow_id,'action':'book',
                      'booking_id':None,'provider_id':provider_id,'old_slot':None,'new_slot':slot,
                      'price_amount':hold['quoted_price'],'price_status':'hold_quote','original_price':None,
                      'new_price_status':'hold_quote','hold_id':hold['hold_id'],
                      'revision':revision,'expires_at':hold['expires_at']}
            db.execute('INSERT INTO workflow_holds VALUES (?,?,?,?,?,?,?)',
                       (hold['hold_id'],workflow_id,revision,provider_id,slot,hold['quoted_price'],hold['expires_at']))
            return self._approval(db,w,snapshot)

    def prepare_change(self, workflow_id, action, booking_id, *, new_slot=None, price_change_requested=False):
        self._check_context()
        if action not in {'cancel','reschedule'}: raise SafetyError('invalid_action')
        if price_change_requested: raise SafetyError('price_unknown')
        if action=='reschedule': new_slot=timestamp(new_slot).isoformat()
        rows=self.provider.list_bookings(self.context.user_id)
        booking=next((b for b in rows if b['id']==booking_id),None)
        if not booking: raise SafetyError('forbidden')
        if booking['status']!='booked': raise SafetyError('booking_not_active')
        with self.store.connect(write=True) as db:
            w=self._owned(db,workflow_id)
            self._editable(db,w)
            if w['booking_id'] and w['booking_id']!=booking_id: raise SafetyError('request_locked')
            original=None
            for op in db.execute("SELECT * FROM operations WHERE user_id=? AND action='book' AND status='COMMITTED'",
                                 (self.context.user_id,)):
                result=json.loads(op['result_json'])
                if result.get('booking_id')==booking_id:
                    original=json.loads(op['snapshot_json'])['price_amount']
            snapshot={'user_id':self.context.user_id,'workflow_id':workflow_id,'action':action,
                      'booking_id':booking_id,'provider_id':booking['provider'],'old_slot':booking['slot'],
                      'new_slot':new_slot if action=='reschedule' else None,'price_amount':original,
                      'price_status':'original_booking_price' if original is not None else 'price_unavailable_from_provider_contract',
                      'original_price':original,'new_price_status':'unavailable_no_fee_mock',
                      'hold_id':None,'revision':w['revision']+1,'expires_at':(self._now()+timedelta(minutes=10)).isoformat()}
            return self._approval(db,w,snapshot)

    def _valid_snapshot(self, db, w, a):
        s=json.loads(a['snapshot_json'])
        if (a['user_id']!=self.context.user_id or s['user_id']!=self.context.user_id
                or s['workflow_id']!=w['workflow_id'] or a['payload_fingerprint']!=fingerprint(s)
                or w['current_approval_id']!=a['approval_id'] or w['revision']!=s['revision']):
            raise SafetyError('approval_invalid')
        if self._now()>=timestamp(s['expires_at']): raise SafetyError('approval_expired')
        if s['action']=='book':
            h=db.execute('SELECT * FROM workflow_holds WHERE hold_id=?',(s['hold_id'],)).fetchone()
            expected=(w['workflow_id'],s['revision'],s['provider_id'],s['new_slot'],s['price_amount'],s['expires_at'])
            if not h or tuple(h[k] for k in ['workflow_id','revision','provider_id','slot','quoted_price','expires_at'])!=expected:
                raise SafetyError('approval_invalid')
            d=json.loads(w['draft_json'])
            if d.get('budget_inr') is not None and s['price_amount']>d['budget_inr']: raise SafetyError('budget_exceeded')
        return s

    def grant_approval(self, workflow_id, approval_id):
        """Explicit trusted customer confirmation of the currently displayed card."""
        if not approval_id: raise SafetyError('approval_required')
        self._check_context()
        with self.store.connect(write=True) as db:
            w=self._owned(db,workflow_id)
            a=db.execute('SELECT * FROM approval_snapshots WHERE approval_id=?',(approval_id,)).fetchone()
            if not a or a['workflow_id']!=workflow_id or a['status']=='VOID': raise SafetyError('approval_invalid')
            if a['user_id']!=self.context.user_id: raise SafetyError('approval_invalid')
            if w['revision']!=a['revision'] or w['current_approval_id']!=approval_id: raise SafetyError('approval_invalid')
            old=db.execute('SELECT * FROM operations WHERE approval_id=?',(approval_id,)).fetchone()
            if old: return old['operation_id']
            if a['status']!='PENDING': raise SafetyError('approval_invalid')
            s=self._valid_snapshot(db,w,a)
            self._editable(db,w,booking=s['action']=='book')
            if s['booking_id'] and db.execute("SELECT 1 FROM operations WHERE booking_id=? AND status IN "
                    "('PREPARED','EXECUTING','OUTCOME_UNKNOWN')",(s['booking_id'],)).fetchone():
                raise SafetyError('request_locked')
            oid=uuid.uuid4().hex
            key='operation-'+oid
            db.execute('INSERT INTO operations (operation_id,workflow_id,user_id,action,booking_id,'
                       'idempotency_key,approval_id,snapshot_json,payload_fingerprint,status) '
                       'VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (oid,workflow_id,self.context.user_id,s['action'],s['booking_id'],key,approval_id,
                        a['snapshot_json'],a['payload_fingerprint'],'PREPARED'))
            db.execute("UPDATE approval_snapshots SET status='GRANTED',approved_at=? WHERE approval_id=?",
                       (self._now().isoformat(),approval_id))
            self._state(db,workflow_id,'EXECUTING')
            return oid

    def confirm(self, workflow_id, approval_id):
        return self.execute(self.grant_approval(workflow_id,approval_id))

    def _operation(self, db, operation_id):
        op=db.execute('SELECT * FROM operations WHERE operation_id=?',(operation_id,)).fetchone()
        if not op or op['user_id']!=self.context.user_id: raise SafetyError('forbidden')
        a=db.execute('SELECT * FROM approval_snapshots WHERE approval_id=?',(op['approval_id'],)).fetchone()
        s=json.loads(op['snapshot_json'])
        w=self._owned(db,op['workflow_id'])
        if (not a or a['status']!='GRANTED' or a['user_id']!=op['user_id']
                or a['workflow_id']!=op['workflow_id'] or a['snapshot_json']!=op['snapshot_json']
                or fingerprint(s)!=op['payload_fingerprint'] or a['payload_fingerprint']!=op['payload_fingerprint']
                or s['action']!=op['action'] or s['user_id']!=self.context.user_id):
            raise SafetyError('approval_invalid')
        return dict(op),s,dict(w)

    def _finish(self, op, state, *, booking=None, reason=None):
        messages={
            'BOOKED':'Booking verified with the provider.',
            'CANCELLED':'Cancellation verified with the provider.',
            'RESCHEDULED':'New appointment slot verified with the provider.',
            'CONFLICT':'Provider reports a conflict. Choose again and approve a new action.',
            'NEEDS_REAPPROVAL':'Action was not completed. Obtain a new quote and approve again.',
            'OUTCOME_UNKNOWN':'Status unverified; no success is claimed. No new booking key will be created.',
            'NOT_ACTIVE':'Provider records show this booking is no longer active.'}
        result={'status':state,'operation_id':op['operation_id'],
                'booking_id':booking['id'] if booking else None,'booking':booking,
                'message':messages[state],'reason':reason}
        with self.store.connect(write=True) as db:
            current,s,w=self._operation(db,op['operation_id'])
            # A completed operation is historical fact; its current read-back may differ.
            if current['status'] not in {'COMMITTED','FAILED'}:
                status='COMMITTED' if state in {'BOOKED','CANCELLED','RESCHEDULED'} else (
                    'OUTCOME_UNKNOWN' if state=='OUTCOME_UNKNOWN' else 'FAILED')
                db.execute('UPDATE operations SET status=?,result_json=?,last_error=?,verified_at=? WHERE operation_id=?',
                           (status,encode(result),reason,self._now().isoformat() if status=='COMMITTED' else None,op['operation_id']))
                if w['revision']==s['revision']:
                    self._state(db,w['workflow_id'],state if state!='NOT_ACTIVE' else 'NEEDS_REAPPROVAL')
                if state=='BOOKED':
                    db.execute('UPDATE workflows SET booking_id=? WHERE workflow_id=?',(booking['id'],w['workflow_id']))
        return result

    def _booking_readback(self, op, s):
        if s['action']=='book':
            status=self.provider.get_booking_status(op['idempotency_key'])
            if status['status']=='booked':
                rows=self.provider.list_bookings(self.context.user_id)
                booking=next((b for b in rows if b['id']==status.get('booking_id')),None)
                if (not booking or booking['status']!='booked' or booking['provider']!=s['provider_id']
                        or booking['slot']!=s['new_slot']):
                    return 'unknown',None
                return 'done',booking
            return status['status'],None
        rows=self.provider.list_bookings(self.context.user_id)
        booking=next((b for b in rows if b['id']==s['booking_id']),None)
        if not booking: return 'unknown',None
        if booking['provider']!=s['provider_id']: return 'unknown',None
        if s['action']=='cancel' and booking['status']=='cancelled': return 'done',booking
        if s['action']=='reschedule' and booking['status']=='booked' and booking['slot']==s['new_slot']: return 'done',booking
        if booking['status']!='booked' or booking['slot']!=s['old_slot']: return 'conflict',booking
        return 'not_found',booking

    def execute(self, operation_id):
        """Single mutation gate; only persisted, granted immutable operations execute."""
        self._check_context()
        with execution_lock(self.path):
            with self.store.connect() as db:
                op,s,w=self._operation(db,operation_id)
            completed={'book':'BOOKED','cancel':'CANCELLED','reschedule':'RESCHEDULED'}[s['action']]
            # Reconcile FIRST on fresh delivery, retries and process restart alike.
            try:
                observed,booking=self._booking_readback(op,s)
            except Exception:
                return self._finish(op,'OUTCOME_UNKNOWN',reason='status_read_unavailable')
            if observed=='done': return self._finish(op,completed,booking=booking)
            if observed=='conflict': return self._finish(op,'CONFLICT',reason='booking_state_changed')
            if op['status']=='COMMITTED':
                return self._finish(op,'NOT_ACTIVE' if observed=='failed' else 'OUTCOME_UNKNOWN',reason='current_state_differs')
            if op['status']=='FAILED':
                return json.loads(op['result_json'])
            if observed=='failed': return self._finish(op,'NEEDS_REAPPROVAL',reason='provider_failed')
            if observed=='unknown': return self._finish(op,'OUTCOME_UNKNOWN',reason='readback_mismatch')
            if op['attempts']>=self.MAX_ATTEMPTS:
                return self._finish(op,'OUTCOME_UNKNOWN',reason='retry_cap_exhausted')
            if self._now()>=timestamp(s['expires_at']):
                # An operation already attempted may still be ambiguous, even after expiry.
                return self._finish(op,'OUTCOME_UNKNOWN' if op['attempts'] else 'NEEDS_REAPPROVAL',reason='approval_expired')
            for _ in range(self.MAX_ATTEMPTS-op['attempts']):
                with self.store.connect(write=True) as db:
                    op,s,w=self._operation(db,operation_id)
                    if w['revision']!=s['revision'] or w['current_approval_id']!=op['approval_id']:
                        raise SafetyError('approval_invalid')
                    # Recheck actual stored hold binding on every delivery, not just grant.
                    a=db.execute('SELECT * FROM approval_snapshots WHERE approval_id=?',(op['approval_id'],)).fetchone()
                    self._valid_snapshot(db,w,a)
                    if op['attempts']>=self.MAX_ATTEMPTS: break
                    db.execute("UPDATE operations SET status='EXECUTING',attempts=attempts+1 WHERE operation_id=?",(operation_id,))
                    self._state(db,w['workflow_id'],'EXECUTING')
                response=None
                error=None
                try:
                    if s['action']=='book': response=self.provider.book(s['hold_id'],op['idempotency_key'])
                    elif s['action']=='cancel': response=self.provider.cancel(s['booking_id'],op['idempotency_key'])
                    else: response=self.provider.reschedule(s['booking_id'],s['new_slot'],op['idempotency_key'])
                except Exception as exc:
                    error=exc
                with self.store.connect(write=True) as db:
                    self._state(db,op['workflow_id'],'VERIFYING')
                try:
                    observed,booking=self._booking_readback(op,s)
                except Exception:
                    return self._finish(op,'OUTCOME_UNKNOWN',reason='status_read_unavailable')
                if observed=='done':
                    if response and s['action']=='book' and response.get('booking_id')!=booking['id']:
                        return self._finish(op,'OUTCOME_UNKNOWN',reason='response_status_mismatch')
                    return self._finish(op,completed,booking=booking)
                if isinstance(error,ProviderError) and error.code in {'slot_taken','hold_expired','slot_conflict'}:
                    return self._finish(op,'CONFLICT' if error.code=='slot_conflict' else 'NEEDS_REAPPROVAL',reason=error.code)
                if observed=='failed': return self._finish(op,'NEEDS_REAPPROVAL',reason='provider_failed')
                if observed in {'conflict','unknown'}: return self._finish(op,'OUTCOME_UNKNOWN',reason='readback_mismatch')
                retryable=isinstance(error,TimeoutError) or (isinstance(error,ProviderError) and error.code=='transient_503')
                if not retryable or self._now()>=timestamp(s['expires_at']):
                    return self._finish(op,'OUTCOME_UNKNOWN',reason='unexpected_error_or_unverified_result')
                # The read above precedes the next iteration; SAME key, durable cap.
            return self._finish(op,'OUTCOME_UNKNOWN',reason='retry_cap_exhausted')

    def recover(self):
        """Embedding startup calls this before accepting new mutations."""
        with self.store.connect() as db:
            ids=[r[0] for r in db.execute("SELECT operation_id FROM operations WHERE user_id=? AND status IN "
                  "('PREPARED','EXECUTING','OUTCOME_UNKNOWN') ORDER BY rowid",(self.context.user_id,))]
        return [self.execute(oid) for oid in ids]
