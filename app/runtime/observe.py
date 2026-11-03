"""Sanitized, versioned JSONL plus real local OTLP export; no raw prompts/memory."""
from contextlib import contextmanager
import contextvars
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import re
from functools import lru_cache
from datetime import datetime,timezone
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
        self.workflow_id=None
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
        allowed={'tool','status','action','operation_hash','generation','exit_reason','error_class','duration_ms','memory_key_hash','state_before','state_after',
                 'idempotency_key_suffix_or_hash','approval_fingerprint_prefix','decision_reason'}
        if span.is_valid:self.last_trace_id=format(span.trace_id,'032x')
        record={'schema_version':2,'run_id':self.run_id,'sequence':self.sequence,
            'timestamp':datetime.now(timezone.utc).isoformat(),'workflow_id':self.workflow_id,
            'trace_id':self.last_trace_id,'span_id':format(span.span_id,'016x'),
            'user_id_hash':hashlib.sha256(self.user_id.encode()).hexdigest(),
            'monotonic_offset_ms':(time.monotonic()-self.started)*1000,
            'model_id':getattr(self,'model_id','scripted'),'prompt_version':getattr(self,'prompt_version','scripted-v1'),'workflow_version':'g2-v1',
            'model_mode':getattr(self,'model_mode','scripted-offline'),
            'policy_version':'g3x-v1','tool_contract_version':'employer-v1','schema_migration_version':3,
            'code_git_sha':build_sha(),'model_call_count':self.models,'tool_call_count':self.tools,
            'token_in':getattr(self,'token_in',None),'token_out':getattr(self,'token_out',None),'cost_usd':None,'event_type':event,
            'model_name_or_scripted':getattr(self,'model_id','scripted'),'model_prompt_version':getattr(self,'prompt_version','scripted-v1'),
            'tool_name':values.get('tool'),'sanitized_args':None,'sanitized_result':None,
            'error_class':None,'idempotency_key_suffix_or_hash':None,'approval_fingerprint_prefix':None,
            'duration_ms':(time.monotonic()-self.started)*1000 if event=='run_exit' else None,
            'decision_reason':None,'exit_reason':None,'state_before':None,'state_after':None,
            'budget_remaining':{'wall_seconds':self.remaining(),'tools':16-self.tools,'models':8-self.models},
            **{k:v for k,v in values.items() if k in allowed}}
        # Accept only explicit metadata, never arbitrary nested caller payloads.
        for field,keys in [('sanitized_args',{'argument_count','payload_sha256','service','area','date_start_ist','date_end_ist','provider_id','slot_ist','hold_id_sha256','idempotency_key_sha256','user_id_sha256','booking_id_sha256'}),
                           ('sanitized_result',{'shape','count','field_count','status','quoted_price'})]:
            if isinstance(values.get(field),dict):record[field]={k:v for k,v in values[field].items() if k in keys}
        def redact(value):
            if isinstance(value,str):
                value=re.sub(r'(?i)bearer\s+[a-z0-9._-]+','Bearer [REDACTED]',value)
                return re.sub(r'(?i)\b(?:gsk_|sk-)[a-z0-9_-]{8,}','[REDACTED]',value)
            if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
            return value
        record=redact(record)
        trace.get_current_span().add_event(event,{k:str(record[k]) for k in allowed if k in record and record[k] is not None})
        encoded=json.dumps(record,sort_keys=True)
        folder=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'traces'; folder.mkdir(exist_ok=True,parents=True)
        with (folder/(self.run_id+'.jsonl')).open('a') as f: f.write(encoded+'\n')
        if self.workflow_id and re.fullmatch('[a-f0-9]{32}',self.workflow_id):
            # An append-only per-workflow projection avoids scanning every other
            # customer's raw trace on each browser poll. Raw run files remain proof.
            index=folder.parent/'activity'/record['user_id_hash'];index.mkdir(parents=True,exist_ok=True)
            with (index/(self.workflow_id+'.jsonl')).open('a') as f:f.write(encoded+'\n')
        return record

@lru_cache(maxsize=1)
def build_sha():
    p=Path('BUILD_INFO.json')
    if not p.exists():return 'UNCOMMITTED'
    metadata=json.loads(p.read_text())
    for name,expected in metadata.get('source_sha256',{}).items():
        source=Path(name)
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            return 'UNCOMMITTED'
    return metadata.get('code_git_sha','UNCOMMITTED')

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
