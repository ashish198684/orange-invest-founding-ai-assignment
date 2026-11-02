"""Run actual SQLite regressions and PG/HTTP/process tests; preserve every attempt."""
import argparse
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
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);a=p.parse_args()
    if not a.label.replace('_','').isalnum():raise ValueError('bad_label')
    out=Path(os.getenv('RUNTIME_STATE','data/runtime'))/'receipts'/a.label;out.mkdir(exist_ok=False,parents=True)
    os.environ['G3X_EVIDENCE_DIR']=str(out/'cases')
    paths=[*ROOT.glob('app/**/*.py'),*ROOT.glob('scripts/*.py'),*ROOT.glob('tests/**/*.py'),*ROOT.glob('tests_g3x/**/*.py'),
           ROOT/'CANONICAL.md',ROOT/'compose.yaml',ROOT/'requirements-g3x.txt']
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with zipfile.ZipFile(out/'source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for path in paths:z.write(path,path.relative_to(ROOT))
    command=[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-v']
    old=subprocess.run(command,cwd=ROOT,capture_output=True)
    (out/'sqlite_stdout.txt').write_bytes(old.stdout);(out/'sqlite_stderr.txt').write_bytes(old.stderr)
    if old.returncode:
        (out/'baseline_failure.json').write_text(json.dumps({'command':command,'exit_code':old.returncode}))
        raise SystemExit('HARD STOP: SQLite baseline regression failed')
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests_g3x'))
    with (out/'pg_tests.txt').open('w') as f:result=unittest.TextTestRunner(verbosity=2,resultclass=Outcome,stream=Tee(f)).run(suite)
    report={'command':[sys.executable,'-X','utf8','scripts/g3x_checks.py','--label',a.label],
            'baseline_command':command,'baseline_exit_code':old.returncode,'baseline_tests':65,
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),'g3x_tests_run':result.testsRun,
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'outcomes':result.outcomes,'source_sha256':hashes,
            'objective_status':'PASS' if result.wasSuccessful() else 'FAIL','acceptance':'CTO review pending'}
    (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'sha256.json').write_text(json.dumps({str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                                            for p in out.rglob('*') if p.is_file()},indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'source_sha256','outcomes'}},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)

if __name__=='__main__':main()
