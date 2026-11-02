"""Eight-method RPC boundary. Child process isolation enforces absolute call deadlines."""
import json
import multiprocessing as mp
import os
from pathlib import Path
import urllib.request
import urllib.error
from app.provider_mock import ProviderError,ProviderTimeout
from app.runtime.observe import active,current_traceparent,tracer,BudgetExceeded

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
        if run: run.charge('tool'); run.emit('provider_start',tool=name)
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
                    if run: run.emit('provider_timeout',tool=name,status='OUTCOME_UNKNOWN')
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
            if run: run.emit('provider_result',tool=name,status='returned')
            return result['result']
    def search_providers(self,service,area,date_range): return self._call('search_providers',(service,area,date_range))
    def get_provider(self,provider_id): return self._call('get_provider',(provider_id,))
    def list_bookings(self,user_id): return self._call('list_bookings',(user_id,))
    def hold_slot(self,provider_id,slot): return self._call('hold_slot',(provider_id,slot))
    def book(self,hold_id,idempotency_key): return self._call('book',(hold_id,idempotency_key))
    def get_booking_status(self,idempotency_key): return self._call('get_booking_status',(idempotency_key,))
    def cancel(self,booking_id,idempotency_key): return self._call('cancel',(booking_id,idempotency_key))
    def reschedule(self,booking_id,new_slot,idempotency_key): return self._call('reschedule',(booking_id,new_slot,idempotency_key))
