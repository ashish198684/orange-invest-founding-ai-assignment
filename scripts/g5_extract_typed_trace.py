"""Promote an unmodified E12 worker trace with typed redacted arguments.
No resequencing, line editing, or live-user data. Requires true worker success.
"""
from pathlib import Path
import hashlib,json,shutil
SRC=Path('/state/receipts/g5_direct_evals_20261103/E12/traces')
OUT=Path('/orange/artifacts/traces/g5_timeout_after_success_typed.jsonl')
RECEIPT=Path('/orange/artifacts/receipts/g5_typed_trace_proof_20261103.json')
assert SRC.is_dir(),'isolated E12 trace source missing'
valid=[]
for p in SRC.glob('*.jsonl'):
    events=[json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
    timeout=any(e.get('event_type')=='provider_timeout' and e.get('tool_name')=='book' for e in events)
    booked=any(e.get('event_type')=='run_exit' and e.get('status')=='BOOKED' for e in events)
    typed=any(e.get('tool_name')=='book' and e.get('event_type')=='provider_start'
              and 'idempotency_key_sha256' in (e.get('sanitized_args') or {})
              and 'hold_id_sha256' in (e.get('sanitized_args') or {}) for e in events)
    if timeout and booked and typed:valid.append((p,events))
assert len(valid)==1,'expected one real worker trace for E12; found '+str(len(valid))
source,events=valid[0]
assert 'gsk_' not in source.read_text() and 'Bearer ' not in source.read_text()
OUT.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(source,OUT)
assert OUT.read_bytes()==source.read_bytes(),'raw bytes altered'
report={'status':'PASS','origin':'isolated offline E12 using real provider + worker',
        'source_filename':source.name,'line_count':len(events),
        'copy_path':str(OUT.relative_to(Path('/orange'))),
        'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
        'has_actual_timeout_after_success':True,
        'has_readback_booked':True,
        'has_typed_hashed_book_arguments':True,
        'not_live_groq':True,
        'unchanged_original':'artifacts/traces/timeout_after_success.jsonl'}
RECEIPT.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,indent=2))
