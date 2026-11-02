"""Sanitized, versioned JSONL plus real local OTLP export; no raw prompts/memory."""
from contextlib import contextmanager
import contextvars
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
from opentelemetry import trace, propagate
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_provider=TracerProvider(resource=Resource.create({'service.name':os.getenv('HOSTNAME','orange-local')}))
_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(timeout=.25)))
trace.set_tracer_provider(_provider)
tracer=trace.get_tracer('orange-invest','3')
active=contextvars.ContextVar('orange_run',default=None)

class BudgetExceeded(TimeoutError): pass

class Run:
    def __init__(self,user_id,wall=18.0):
        self.user_id=user_id; self.wall=wall; self.started=time.monotonic()
        self.run_id=uuid.uuid4().hex; self.tools=0; self.models=0; self.sequence=0
        self.closed=False;self.last_trace_id='0'*32
    def remaining(self): return max(0,self.wall-(time.monotonic()-self.started))
    def charge(self,kind):
        if self.remaining()<=0: raise BudgetExceeded('wall_limit')
        if kind=='tool':
            if self.tools>=16:raise BudgetExceeded('tool_limit')
            self.tools+=1
        elif kind=='model':
            if self.models>=8:raise BudgetExceeded('model_limit')
            self.models+=1
    def emit(self,event,**values):
        if event=='run_exit':
            if self.closed:return None
            self.closed=True
        self.sequence+=1
        span=trace.get_current_span().get_span_context()
        # Only explicit safe metadata is accepted; never serialize caller payloads.
        allowed={'tool','status','action','operation_hash','generation','exit_reason','error_class','duration_ms','memory_key_hash','state_before','state_after'}
        if span.is_valid:self.last_trace_id=format(span.trace_id,'032x')
        record={'schema_version':1,'run_id':self.run_id,'sequence':self.sequence,
            'trace_id':self.last_trace_id,'span_id':format(span.span_id,'016x'),
            'user_id_hash':hashlib.sha256(self.user_id.encode()).hexdigest(),
            'monotonic_offset_ms':(time.monotonic()-self.started)*1000,
            'model_id':'scripted','prompt_version':'scripted-v1','workflow_version':'g2-v1',
            'policy_version':'g3x-v1','tool_contract_version':'employer-v1','schema_migration_version':1,
            'code_git_sha':build_sha(),'model_call_count':self.models,'tool_call_count':self.tools,
            'token_in':None,'token_out':None,'cost_usd':None,'event_type':event,
            'budget_remaining':{'wall_seconds':self.remaining(),'tools':16-self.tools,'models':8-self.models},
            **{k:v for k,v in values.items() if k in allowed}}
        trace.get_current_span().add_event(event,{k:str(v) for k,v in values.items() if k in allowed})
        encoded=json.dumps(record,sort_keys=True)
        folder=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'traces'; folder.mkdir(exist_ok=True,parents=True)
        with (folder/(self.run_id+'.jsonl')).open('a') as f: f.write(encoded+'\n')
        return record

def build_sha():
    p=Path('BUILD_INFO.json')
    return json.loads(p.read_text()).get('code_git_sha','UNCOMMITTED') if p.exists() else 'UNCOMMITTED'

def current_traceparent():
    carrier={}; propagate.inject(carrier)
    return carrier.get('traceparent','')

@contextmanager
def scope(run,name,parent=None):
    token=active.set(run)
    with tracer.start_as_current_span(name,context=propagate.extract({'traceparent':parent}) if parent else None,
                                     record_exception=False,set_status_on_exception=False) as span:
        span.set_attribute('run.id',run.run_id)
        span.set_attribute('user.hash',hashlib.sha256(run.user_id.encode()).hexdigest())
        try: yield span
        finally: active.reset(token)
