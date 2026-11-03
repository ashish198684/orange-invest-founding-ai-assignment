"""Eight-method RPC boundary. Child process isolation enforces absolute call deadlines."""
import json
import hashlib
import time
import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore
from app.provider_mock import ProviderError,ProviderTimeout
from app.runtime.observe import active,current_traceparent,tracer,BudgetExceeded
_slots=BoundedSemaphore(3)

def sanitized_tool_arguments(name,args):
    """Typed, bounded tool-argument evidence; never emits raw user IDs or operation keys."""
    from app.provider_mock.fixtures import IST
    digest=lambda v: hashlib.sha256(str(v).encode()).hexdigest()
    record={'argument_count':len(args),
            'payload_sha256':hashlib.sha256(json.dumps(args,sort_keys=True).encode()).hexdigest()}
    def local_time(value):
        if not isinstance(value,str) or len(value)>40:return '[redacted]'
        try:
            stamp=datetime.fromisoformat(value)
            return stamp.astimezone(IST).isoformat() if stamp.tzinfo is not None else '[redacted]'
        except ValueError:return '[redacted]'
    def mock_provider_id(value):
        if isinstance(value,str) and re.fullmatch(r'(?:plumber|electrician|ac)[a-z0-9_-]{1,28}',value):
            return value
        return '[redacted]'
    if name=='search_providers' and len(args)==3:
        record['service']=args[0] if args[0] in ('plumber','electrician','ac servicing') else '[unsupported]'
        record['area']=args[1] if args[1] in ('Indiranagar','Koramangala') else '[unsupported]'
        window=args[2] if isinstance(args[2],dict) else {}
        record['date_start_ist']=local_time(window.get('start'))
        record['date_end_ist']=local_time(window.get('end'))
    elif name=='get_provider' and len(args)==1:
        record['provider_id']=mock_provider_id(args[0])
    elif name=='list_bookings' and len(args)==1:
        record['user_id_sha256']=digest(args[0])
    elif name=='hold_slot' and len(args)==2:
        record['provider_id']=mock_provider_id(args[0])
        record['slot_ist']=local_time(args[1])
    elif name=='book' and len(args)==2:
        record['hold_id_sha256']=digest(args[0])
        record['idempotency_key_sha256']=digest(args[1])
    elif name=='get_booking_status' and len(args)==1:
        record['idempotency_key_sha256']=digest(args[0])
    elif name=='cancel' and len(args)==2:
        record['booking_id_sha256']=digest(args[0])
        record['idempotency_key_sha256']=digest(args[1])
    elif name=='reschedule' and len(args)==3:
        record['booking_id_sha256']=digest(args[0])
        record['slot_ist']=local_time(args[1])
        record['idempotency_key_sha256']=digest(args[2])
    return record

def settings():
    return json.loads((Path(os.getenv('RUNTIME_STATE','data/runtime'))/'runtime.json').read_text())

class ProviderClient:
    def __init__(self,user_id,*,timeout=5): self.user_id=user_id; self.timeout=timeout
    def _call(self,name,args):
        run=active.get()
        if run:run.charge('tool')
        if not _slots.acquire(timeout=run.remaining() if run else self.timeout):raise BudgetExceeded('provider_capacity')
        started=time.monotonic()
        key=hashlib.sha256(args[-1].encode()).hexdigest() if name in {'book','cancel','reschedule','get_booking_status'} else None
        if run:run.emit('provider_start',tool=name,idempotency_key_suffix_or_hash=key,
                        sanitized_args=sanitized_tool_arguments(name,args))
        try:
            result=self._rpc(name,args)
            summary={'shape':'list' if isinstance(result,list) else 'object','count':len(result) if isinstance(result,list) else None}
            if isinstance(result,dict):
                if result.get('status') in {'booked','not_found','failed','cancelled'}:summary['status']=result['status']
                if type(result.get('quoted_price')) in {int,float}:summary['quoted_price']=result['quoted_price']
            if run:run.emit('provider_result',tool=name,status='returned',duration_ms=(time.monotonic()-started)*1000,
                            sanitized_result=summary,idempotency_key_suffix_or_hash=key)
            return result
        except Exception as exc:
            if run:run.emit('provider_timeout' if isinstance(exc,ProviderTimeout) else 'provider_error',tool=name,
                            error_class=type(exc).__name__,status='OUTCOME_UNKNOWN',idempotency_key_suffix_or_hash=key,
                            duration_ms=(time.monotonic()-started)*1000)
            raise
        finally:_slots.release()
    def _rpc(self,name,args):
        run=active.get()
        limit=min(self.timeout,run.remaining() if run else self.timeout)
        if limit<=0: raise BudgetExceeded('wall_limit')
        with tracer.start_as_current_span('provider.'+name):
            payload={'url':os.getenv('PROVIDER_URL','http://provider:8090')+'/rpc',
                     'body':{'method':name,'args':list(args),'user_id':self.user_id},
                     'secret':settings()['provider_secret'],'parent':current_traceparent()}
            # A minimal child avoids importing the calling worker/controller and
            # OTel stack on every RPC. Secrets travel on stdin, never argv/logs.
            child=subprocess.Popen([sys.executable,'-m','app.runtime.rpc_transport'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                raw,_=child.communicate(json.dumps(payload).encode(),timeout=limit)
                if child.returncode:raise ProviderError('transport_unavailable',503)
                result=json.loads(raw)
            except subprocess.TimeoutExpired:
                child.kill();child.communicate(timeout=.3);raise ProviderTimeout() from None
            finally:
                if child.poll() is None:child.kill();child.communicate(timeout=.3)
            if 'error' in result:
                if result['error']=='timeout': raise ProviderTimeout()
                raise ProviderError(result['error'],result.get('http_status',503))
            if name=='search_providers' and len(result['result'])>8:raise ProviderError('candidate_limit',400)
            return result['result']
    def search_providers(self,service,area,date_range): return self._call('search_providers',(service,area,date_range))
    def get_provider(self,provider_id): return self._call('get_provider',(provider_id,))
    def list_bookings(self,user_id): return self._call('list_bookings',(user_id,))
    def hold_slot(self,provider_id,slot): return self._call('hold_slot',(provider_id,slot))
    def book(self,hold_id,idempotency_key): return self._call('book',(hold_id,idempotency_key))
    def get_booking_status(self,idempotency_key): return self._call('get_booking_status',(idempotency_key,))
    def cancel(self,booking_id,idempotency_key): return self._call('cancel',(booking_id,idempotency_key))
    def reschedule(self,booking_id,new_slot,idempotency_key): return self._call('reschedule',(booking_id,new_slot,idempotency_key))
