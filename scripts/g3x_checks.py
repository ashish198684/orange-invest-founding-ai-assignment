"""Run actual SQLite regressions and PG/HTTP/process tests; preserve every attempt."""
import argparse
import base64
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
class Outcome(unittest.TextTestResult):
    def __init__(self,*args,**kw):super().__init__(*args,**kw);self.outcomes={}
    def addSuccess(self,t):super().addSuccess(t);self.outcomes.setdefault(t.id(),'PASS')
    def addFailure(self,t,e):super().addFailure(t,e);self.outcomes[t.id()]='FAIL'
    def addError(self,t,e):super().addError(t,e);self.outcomes[t.id()]='ERROR'
    def addSkip(self,t,r):super().addSkip(t,r);self.outcomes[t.id()]='SKIP'
    def addSubTest(self,t,s,e):
        super().addSubTest(t,s,e)
        if e:self.outcomes[t.id()]='FAIL'

class Tee:
    def __init__(self,file):self.file=file
    def write(self,v):sys.stderr.write(v);self.file.write(v);self.file.flush()
    def flush(self):sys.stderr.flush();self.file.flush()

def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--match');a=p.parse_args()
    if not a.label.replace('_','').isalnum():raise ValueError('bad_label')
    out=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'receipts'/a.label;out.mkdir(exist_ok=False,parents=True)
    os.environ['G3X_EVIDENCE_DIR']=str(out/'cases')
    paths=[*ROOT.glob('app/**/*.py'),*ROOT.glob('scripts/*.py'),*ROOT.glob('tests/**/*.py'),*ROOT.glob('tests_g3x/**/*.py'),
           ROOT/'CANONICAL.md',ROOT/'compose.yaml',ROOT/'requirements-g3x.txt']
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with zipfile.ZipFile(out/'source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for path in paths:z.write(path,path.relative_to(ROOT))
    command=[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-v']
    check_command=[sys.executable,'-X','utf8','scripts/check_contract.py']
    check=subprocess.run(check_command,cwd=ROOT,capture_output=True)
    (out/'g0_stdout.json').write_bytes(check.stdout);(out/'g0_stderr.txt').write_bytes(check.stderr)
    if check.returncode:raise SystemExit('HARD STOP: canonical integrity failed')
    old=subprocess.run(command,cwd=ROOT,capture_output=True)
    (out/'sqlite_stdout.txt').write_bytes(old.stdout);(out/'sqlite_stderr.txt').write_bytes(old.stderr)
    if old.returncode:
        (out/'baseline_failure.json').write_text(json.dumps({'command':command,'exit_code':old.returncode}))
        raise SystemExit('HARD STOP: SQLite baseline regression failed')
    suite=(unittest.defaultTestLoader.loadTestsFromName(a.match) if a.match
           else unittest.defaultTestLoader.discover(str(ROOT/'tests_g3x')))
    with (out/'pg_tests.txt').open('w') as f:result=unittest.TextTestRunner(verbosity=2,resultclass=Outcome,stream=Tee(f)).run(suite)
    with (out/'g3x_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['scenario','expected','actual','pass_fail','notes']);writer.writeheader()
        writer.writerows({'scenario':name,'expected':'Executable PG/auth/privacy/budget invariants hold','actual':status,
                         'pass_fail':status,'notes':'G3X conformance; not G4 scripted-user evaluations'} for name,status in result.outcomes.items())
    correlations=[json.loads(p.read_text()) for p in (out/'cases').glob('*/correlation.json')]
    actors={r['actor_hash'] for r in correlations};trace_ids=set();trace_dir=out/'traces';trace_dir.mkdir()
    state=Path(os.environ.get('RUNTIME_STATE','data/runtime'))
    for p in (state/'traces').glob('*.jsonl'):
        events=[json.loads(line) for line in p.read_text().splitlines()]
        if any(e.get('user_id_hash') in actors for e in events):
            (trace_dir/p.name).write_bytes(p.read_bytes());trace_ids.update(e['trace_id'] for e in events)
    frames=[json.loads(line) for line in (state/'otel.jsonl').read_text().splitlines()] if (state/'otel.jsonl').exists() else []
    for frame in frames:
        for resource in frame.get('resourceSpans',[]):
            for library in resource.get('scopeSpans',[]):
                for span in library.get('spans',[]):
                    if any(a.get('key')=='user.hash' and a.get('value',{}).get('stringValue') in actors for a in span.get('attributes',[])):
                        trace_ids.add(base64.b64decode(span['traceId']).hex())
    exported=[]
    for frame in frames:
        for resource in frame.get('resourceSpans',[]):
            for library in resource.get('scopeSpans',[]):
                for span in library.get('spans',[]):
                    if base64.b64decode(span['traceId']).hex() in trace_ids:exported.append(span)
    (out/'otel_spans.json').write_text(json.dumps(exported,indent=2)+'\n')
    report={'command':[sys.executable,'-X','utf8','scripts/g3x_checks.py','--label',a.label]+(['--match',a.match] if a.match else []),
            'code_git_sha':json.loads((ROOT/'BUILD_INFO.json').read_text())['code_git_sha'] if (ROOT/'BUILD_INFO.json').exists() else 'UNCOMMITTED',
            'baseline_command':command,'baseline_exit_code':old.returncode,'baseline_tests':65,
            'source_check_command':check_command,'source_check_exit_code':check.returncode,
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),'g3x_tests_run':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'outcomes':result.outcomes,'source_sha256':hashes,
            'exported_otel_spans':len(exported),'exported_jsonl_files':len(list(trace_dir.glob('*.jsonl'))),
            'objective_status':'PASS' if result.wasSuccessful() else 'FAIL','acceptance':'CTO review pending'}
    (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'sha256.json').write_text(json.dumps({str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                                            for p in out.rglob('*') if p.is_file()},indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'source_sha256','outcomes'}},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':main()
