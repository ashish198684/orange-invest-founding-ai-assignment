"""Independent provider service/role. Fault configuration is test-admin SQL only."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hmac
import json
import time
import os
from app.provider_mock import ProviderMock,ProviderError,ScenarioConfig
from app.runtime.pg import PgStore
from app.runtime.provider_client import settings
from app.runtime.observe import Run,scope

METHODS={'search_providers','get_provider','list_bookings','hold_slot','book','get_booking_status','cancel','reschedule'}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def answer(self,status,result):
        body=json.dumps(result).encode(); self.send_response(status); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body))); self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self): self.answer(200,{'status':'provider-ready'})
    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('X-Provider-Key',''),settings()['provider_secret']):
            return self.answer(403,{'error':'forbidden'})
        try:
            value=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),65536)))
            method=value['method']; uid=value['user_id']
            if method not in METHODS or not isinstance(uid,str): raise ValueError()
            p=ProviderMock('unused',user_id=uid,store=PgStore(uid,role='orange_provider'))
            with p.store.connect() as db:
                row=db.execute('SELECT config_json FROM fault_settings WHERE user_id=?',(uid,)).fetchone()
            fault=json.loads(row[0]) if row else {}
            values={k:v for k,v in fault.items() if k in {'book_branch','quote_delta','reschedule_conflicts','seed','scenario_id'}}
            if 'reschedule_conflicts' in values: values['reschedule_conflicts']=tuple(values['reschedule_conflicts'])
            p.config=ScenarioConfig(**values)
            with scope(Run(uid),'provider.server.'+method,self.headers.get('traceparent')):
                if fault.get('hang_method')==method: time.sleep(float(fault.get('delay',25)))
                result=getattr(p,method)(*value['args'])
                if fault.get('terminate_after_method')==method:os._exit(41)
                if fault.get('response_loss_method')==method: time.sleep(float(fault.get('delay',25)))
                self.answer(200,{'result':result})
        except ProviderError as exc:self.answer(exc.http_status,{'error':exc.code,'http_status':exc.http_status})
        except Exception:self.answer(500,{'error':'provider_unavailable','http_status':503})

if __name__=='__main__':
    ThreadingHTTPServer.request_queue_size=128
    ThreadingHTTPServer(('0.0.0.0',8090),Handler).serve_forever()
