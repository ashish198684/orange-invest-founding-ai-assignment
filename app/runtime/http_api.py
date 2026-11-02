"""G3X authenticated HTTP contract. No browser UI or live LLM is implemented here."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
import os
import uuid
from app.workflow import SafetyError
from app.provider_mock import ProviderError
from app.runtime.controller import PgController
from app.runtime.pg import PgStore
from app.runtime.observe import Run,scope,BudgetExceeded
from app.runtime.security import login,authenticate,check_csrf,hashed
from app.runtime.memory import Memory

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def answer(self,status,value,cookie=None):
        body=json.dumps(value,default=str).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        if cookie:self.send_header('Set-Cookie','orange_session='+cookie+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=7200'+('; Secure' if os.getenv('HTTPS_MODE')=='1' else ''))
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def dispatch(self):
        if self.path=='/health':return self.answer(200,{'status':'api-ready'})
        run=Run('anonymous');status=200;result={};cookie=None
        try:
            self.connection.settimeout(2)
            size=int(self.headers.get('Content-Length',0))
            if size>65536:raise ValueError('request_too_large')
            value=json.loads(self.rfile.read(size)) if size else {}
            if self.path=='/health':return self.answer(200,{'status':'api-ready'})
            if self.path=='/login' and self.command=='POST':
                if set(value)!={'username','password'}:raise ValueError('invalid_login')
                if self.headers.get('Origin') not in {'http://127.0.0.1:8080','http://127.0.0.1:8081','http://127.0.0.1:8082'}:raise PermissionError('origin_denied')
                cookie,csrf=login(value['username'],value['password'])
                return self.answer(200,{'csrf_token':csrf,'local_demo_only':True},cookie)
            session=authenticate(self.headers.get('Cookie',''));uid=session['user_id'];run.user_id=uid
            if self.command!='GET':check_csrf(session,self.headers.get('X-CSRF-Token',''),self.headers.get('Origin',''))
            if set(value)&{'user_id','approved','idempotency_key','tool','sql'}:raise PermissionError('untrusted_fields')
            parts=self.path.strip('/').split('/')
            c=PgController(uid)
            with scope(run,'api.'+self.command+'.'+parts[0]):
                run.emit('request_start')
                if parts==['workflows'] and self.command=='POST':
                    result=c.create_request(value['logical_request_id'],**value.get('draft',{}))
                elif parts[0]=='workflows' and len(parts)>=2:
                    wid=parts[1]
                    if len(wid)==32 and all(ch in '0123456789abcdef' for ch in wid):run.workflow_id=wid
                    if self.command=='GET':result=c.view(wid)
                    elif len(parts)==2 and self.command=='PATCH':result=c.correct(wid,**value['draft'])
                    elif parts[-1]=='search':result=c.search(wid)
                    elif parts[-1]=='hold':result=c.prepare_booking(wid,value['provider_id'],value['slot'])
                    elif parts[-1]=='change':result=c.prepare_change(wid,value['action'],value['booking_id'],
                        new_slot=value.get('new_slot'),price_change_requested=value.get('price_change_requested',False))
                    elif parts[-1]=='chat':
                        result=c.chat(wid,value['text'])
                    else:raise ValueError('unknown_route')
                elif parts[0]=='approvals' and len(parts)>=2:
                    aid=parts[1]
                    with c.store.connect(write=self.command!='GET') as db:
                        a=db.execute('SELECT * FROM approval_snapshots WHERE approval_id=?',(aid,)).fetchone()
                        if not a:raise PermissionError('forbidden')
                        w=c._owned(db,a['workflow_id'])
                        run.workflow_id=w['workflow_id']
                        c._valid_snapshot(db,w,a)
                    if self.command=='GET':
                        card=uuid.uuid4().hex
                        with c.store.connect(write=True) as db:
                            db.execute('INSERT INTO issued_cards VALUES(?,?,?,?,?,?,?)',
                                (card,uid,session['session_hash'],aid,a['payload_fingerprint'],a['revision'],a['expires_at']))
                        result={'card_id':card,'approval_id':aid,'snapshot':json.loads(a['snapshot_json']),
                                'fingerprint':a['payload_fingerprint'],'revision':a['revision'],'evidence':'issued; not proof of human perception'}
                        run.emit('approval_card_issued',approval_fingerprint_prefix=a['payload_fingerprint'][:12])
                    elif parts[-1]=='confirm':
                        with c.store.connect() as db:
                            card=db.execute('SELECT * FROM issued_cards WHERE card_id=? AND session_hash=? AND approval_id=?',
                                (value.get('card_id'),session['session_hash'],aid)).fetchone()
                        if not card or card['fingerprint']!=value.get('fingerprint') or card['revision']!=value.get('revision'):
                            raise PermissionError('card_absent_stale_or_forged')
                        if 'snapshot' in value and value['snapshot']!=json.loads(a['snapshot_json']):
                            raise PermissionError('card_snapshot_mismatch')
                        op=c.grant_approval(a['workflow_id'],aid)
                        result={'status':'PENDING_VERIFICATION','operation_id':op,'message':'Approval recorded. Provider outcome is not yet verified.'}
                        run.emit('approval_granted',operation_hash=hashed(op),approval_fingerprint_prefix=a['payload_fingerprint'][:12])
                    else:raise ValueError('unknown_route')
                elif parts[0]=='operations' and len(parts)==2 and self.command=='GET':
                    with c.store.connect() as db:op=db.execute('SELECT * FROM operations WHERE operation_id=?',(parts[1],)).fetchone()
                    if not op:raise PermissionError('forbidden')
                    run.workflow_id=op['workflow_id']
                    result=json.loads(op['result_json']) if op['result_json'] else {'status':'PENDING_VERIFICATION','operation_id':parts[1],'message':'Provider outcome is not yet verified.'}
                elif parts==['memory']:
                    memory=Memory(uid)
                    result=memory.view() if self.command=='GET' else memory.update(**value)
                elif parts[0]=='context' and self.command=='GET':result=Memory(uid).context()
                elif parts[0]=='traces' and len(parts)==2 and self.command=='GET':
                    with c.store.connect() as db:
                        result=[json.loads(r[0]) for r in db.execute('SELECT event_json FROM trace_events WHERE run_id=? ORDER BY event_id',(parts[1],))]
                    if not result:raise PermissionError('forbidden')
                    from pathlib import Path
                    if len(parts[1])==32 and all(ch in '0123456789abcdef' for ch in parts[1]):
                        path=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'traces'/(parts[1]+'.jsonl')
                        if path.exists():result=[json.loads(line) for line in path.read_text().splitlines()]
                else:raise ValueError('unknown_route')
                final=run.emit('run_exit',exit_reason='response',status=result.get('status','returned') if isinstance(result,dict) else 'returned',
                               decision_reason=result.get('message') if isinstance(result,dict) else 'Read-only result returned.')
                with c.store.connect(write=True) as db:
                    db.execute('INSERT INTO trace_events(user_id,run_id,trace_id,event_json) VALUES(?,?,?,?)',(uid,run.run_id,final['trace_id'],json.dumps(final)))
                if isinstance(result,dict):result={**result,'run_id':run.run_id,'trace_id':final['trace_id']}
        except PermissionError as exc:status=403;result={'error':str(exc),'message':'Request denied.'}
        except (SafetyError,ProviderError) as exc:
            status=403 if exc.code=='forbidden' else 409
            result={'error':exc.code,'message':'No unapproved action was performed.'}
        except BudgetExceeded:status=202;result={'status':'OUTCOME_UNKNOWN','message':'Response limit reached; refresh the same request to verify its status.'}
        except TimeoutError:
            status=503;result={'error':'capacity_unavailable','message':'Capacity unavailable. Retry the same logical request; no success is claimed.'}
        except Exception as exc:
            run.emit('handler_error',error_class=type(exc).__name__)
            status=400;result={'error':'invalid_or_unavailable','message':'Request could not be verified; no success is claimed.'}
        finally:
            if result is None:result={}
            if not run.closed:run.emit('run_exit',exit_reason='denied_or_error',status=str(status))
        self.answer(status,result,cookie)
    do_GET=dispatch;do_POST=dispatch;do_PATCH=dispatch

if __name__=='__main__':
    ThreadingHTTPServer.request_queue_size=256
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
