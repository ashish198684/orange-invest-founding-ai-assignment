"""Bound G2 tests, synthetic state observations and immutable source to a receipt."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--require-committed',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch('[a-z0-9_]+',args.label): parser.error('Invalid label')
    out=ROOT/'artifacts/receipts'/args.label
    out.mkdir(exist_ok=False)
    files=sorted([*ROOT.glob('app/**/*.py'),*ROOT.glob('tests/**/*.py'),*ROOT.glob('scripts/*.py'),
                  ROOT/'CANONICAL.md',ROOT/'AGENTS.md',ROOT/'DECISIONS.md',ROOT/'requirements.txt'])
    source={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    head=git('rev-parse','HEAD').decode().strip()
    mismatch=[]
    for rel in source:
        run=subprocess.run(['git','show',f'{head}:{rel}'],cwd=ROOT,capture_output=True)
        if run.returncode or hashlib.sha256(run.stdout).hexdigest()!=source[rel]: mismatch.append(rel)
    if args.require_committed and mismatch: raise SystemExit(f'Uncommitted source: {mismatch}')
    with zipfile.ZipFile(out/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for p in files: archive.write(p,p.relative_to(ROOT))
    pre=json.loads((ROOT/'artifacts/receipts/p1_preflight_20261101.json').read_text())
    historical={**pre['historical_evidence_sha256'],
                **json.loads((ROOT/'artifacts/receipts/p1_postcommit_20261101/sha256.json').read_text())}
    assert all(sha(ROOT/p)==h for p,h in historical.items()),'Historical evidence changed'
    commands=[]
    def run(label,arguments,env=None):
        command=[sys.executable,'-X','utf8',*arguments]
        process=subprocess.run(command,cwd=ROOT,capture_output=True,env=env)
        (out/f'{label}_stdout.txt').write_bytes(process.stdout)
        (out/f'{label}_stderr.txt').write_bytes(process.stderr)
        commands.append({'command':command,'exit_code':process.returncode})
        return process
    contract=run('g0',['scripts/check_contract.py'])
    env={**os.environ,'G2_EVIDENCE_DIR':str(out/'cases')}
    tests=run('tests',['scripts/test_results.py',str(out)],env)
    probe=run('probe',['scripts/controller_probe.py',str(out/'timeout_probe')]) if tests.returncode==0 else None
    inspection=run('independent_db_checks',['scripts/inspect_g2.py',str(out)]) if probe and probe.returncode==0 else None
    diff=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True)
    (out/'diff_check.txt').write_bytes(diff.stdout+diff.stderr)
    (out/'git_status.txt').write_bytes(git('status','--short'))
    assert all(sha(ROOT/p)==h for p,h in source.items()),'Sources changed during test run'
    assert all(sha(ROOT/p)==h for p,h in historical.items()),'Historical evidence changed during tests'
    report=json.loads((out/'test_results.json').read_text())
    failed=bool(contract.returncode or tests.returncode or not probe or probe.returncode or
                not inspection or inspection.returncode or diff.returncode)
    receipt=dict(gate='G2',objective_status='FAIL' if failed else 'PASS',acceptance='CTO review pending',
        source_commit=head,source_matches_commit=not mismatch,uncommitted_source=mismatch,commands=commands,
        tests_run=report['tests_run'],passed=report['passed'],failures=report['failures'],errors=report['errors'],skipped=report['skipped'],
        g1_provider_tests=sum('test_provider_contract' in r['scenario'] for r in report['rows']),
        g2_controller_tests=sum('test_g2_safety' in r['scenario'] for r in report['rows']),
        source_sha256=source,historical_evidence_unchanged=True,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,sqlite=sqlite3.sqlite_version,platform=platform.platform(),
        seed=20261101,controlled_clock='2026-11-01T09:00:00+05:30',diff_check_exit_code=diff.returncode,
        unresolved_failures=[r['scenario'] for r in report['rows'] if r['pass_fail']!='PASS'],
        later_gates={'G3':'NOT_STARTED','G4':'NOT_STARTED','G5':'NOT_STARTED','Groq':'NOT_IMPLEMENTED'},
        claims_boundary='G2 acceptance tests; not the employer G4 scripted-agent evaluation count')
    write(out/'receipt.json',receipt)
    write(out/'sha256.json',{p.relative_to(ROOT).as_posix():sha(p) for p in out.rglob('*')
                          if p.is_file() and not p.name.endswith('.controller.lock')})
    print(json.dumps({k:v for k,v in receipt.items() if k!='source_sha256'},indent=2))
    raise SystemExit(int(failed))

if __name__=='__main__': main()
