"""Eight-method RPC boundary. Child process isolation enforces absolute call deadlines."""
import json
import hashlib
import time
import multiprocessing as mp
import os
from pathlib import Path
import urllib.request
import urllib.error
from threading import BoundedSemaphore
from app.provider_mock import ProviderError,ProviderTimeout
from app.runtime.observe import active,current_traceparent,tracer,BudgetExceeded
_slots=BoundedSemaphore(3)

def settings():
    return json.loads((Path(os.getenv('RUNTIME_STATE','data/runtime'))/'runtime.json').read_text())

def _request_child(pipe,url,body,secret,parent):
    try:
        request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={
            'Content-Type':'application/json','X-Provider-Key':secret,'traceparent':parent})
        try:
            with urllib.request.urlopen(request,timeout=15) as response: data=json.load(response)
        except urllib.error.HTTPError as exc: data=json.loads(exc.read())
        pipe.send(data)
    except BaseException:
        pipe.send({'error':'transport_unavailable','http_status':503})
    finally: pipe.close()

class ProviderClient:
    def __init__(self,user_id,*,timeout=5): self.user_id=user_id; self.timeout=timeout
    def _call(self,name,args):
        run=active.get()
        if run:run.charge('tool')
        if not _slots.acquire(timeout=run.remaining() if run else self.timeout):raise BudgetExceeded('provider_capacity')
        started=time.monotonic()
        key=hashlib.sha256(args[-1].encode()).hexdigest() if name in {'book','cancel','reschedule','get_booking_status'} else None
        if run:run.emit('provider_start',tool=name,idempotency_key_suffix_or_hash=key,
                        sanitized_args={'argument_count':len(args),'payload_sha256':hashlib.sha256(json.dumps(args,sort_keys=True).encode()).hexdigest()})
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
            context=mp.get_context('spawn')
            recv,send=context.Pipe(duplex=False)
            child=context.Process(target=_request_child,args=(send,os.getenv('PROVIDER_URL','http://provider:8090')+'/rpc',
                 {'method':name,'args':list(args),'user_id':self.user_id},settings()['provider_secret'],current_traceparent()))
            child.start(); send.close()
            try:
                if not recv.poll(limit):
                    raise ProviderTimeout()
                result=recv.recv()
            finally:
                if child.is_alive(): child.terminate()
                child.join(timeout=.3)
                if child.is_alive(): child.kill(); child.join(timeout=.3)
                recv.close()
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
