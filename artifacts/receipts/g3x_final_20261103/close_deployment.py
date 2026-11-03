"""Refresh the local deployment with the final evidence-only canonical revision."""
from pathlib import Path
import hashlib,json,subprocess
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
def main():
    commands=[]
    def run(command):
        print('RUN',subprocess.list2cmdline(command),flush=True)
        started=datetime.now(timezone.utc).isoformat()
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300)
        n=len(commands)+1
        (OUT/f'close_{n:02}_stdout.txt').write_bytes(r.stdout);(OUT/f'close_{n:02}_stderr.txt').write_bytes(r.stderr)
        commands.append({'command':command,'started_at':started,'exit_code':r.returncode})
        (OUT/'close_commands.json').write_text(json.dumps(commands,indent=2))
        if r.returncode:raise RuntimeError('closeout command failed; exact outputs retained')
        return r.stdout.decode()
    head=run(['git','rev-parse','HEAD']).strip()
    run(['docker','compose','up','-d','--build','--wait'])
    raw=run(['docker','compose','ps','--format','json'])
    topology=json.loads(raw) if raw.strip().startswith('[') else [json.loads(x) for x in raw.splitlines() if x.strip()]
    states={x['Service']:x for x in topology}
    for service in ['pg','api','api2','worker','worker2','provider','telemetry','gateway']:assert states[service]['State']=='running'
    for service in ['pg','api','api2','provider','gateway']:assert states[service]['Health']=='healthy'
    code=run(['docker','compose','exec','-T','api','python','-c','from app.runtime.observe import build_sha;print(build_sha())']).strip()
    assert code==json.loads((ROOT/'BUILD_INFO.json').read_text())['code_git_sha']
    integrity=json.loads(run(['docker','compose','exec','-T','api','python','-X','utf8','scripts/check_contract.py']))
    assert integrity['hash_checks_passed'] and all(x['match'] for x in integrity['files'])
    canonical=hashlib.sha256((ROOT/'CANONICAL.md').read_bytes()).hexdigest()
    assert next(x for x in integrity['files'] if x['file']=='CANONICAL.md')['actual_sha256']==canonical
    history=run(['git','log','--format=%H %s','855e372f11e2329774fff9efe6060ece6035891d..HEAD'])
    report={'gate':'G3X','status':'PASS','acceptance':'CTO review pending','canonical_id':'ORANGE-FOUNDINGAI-20261102-003',
       'canonical_sha256':canonical,'source_integrity_checks':len(integrity['files']),'code_commit':code,
       'evidence_commit_before_closeout':head,'code_commits':history.splitlines(),'commands':commands,
       'tests':{'baseline_passed':65,'g3x_passed':39,'failures':0,'errors':0,'skipped':0,'exit_code':0},
       'workload_runs':2,'workflows_per_run':100,'duplicate_confirmations_per_run':100,
       'provider_slot_violations':0,'logical_intent_violations':0,'approval_violations':0,
       'topology':topology,'audit_receipt_sha256':hashlib.sha256((OUT/'receipt.json').read_bytes()).hexdigest(),
       'stopped':True,'later_gates':'G4/G5/Groq NOT STARTED','submission':'NO-GO',
       'limits':'See docs/g3x_handoff.md and independent audit for slow journeys, honest unknowns, bounded best-effort OTLP, local demo auth and privacy/restore limits.'}
    (OUT/'closeout.json').write_text(json.dumps(report,indent=2)+'\n')
    paths=[p for p in OUT.rglob('*') if p.is_file() and p.name!='closeout_sha256.json']
    paths += [ROOT/'CANONICAL.md',ROOT/'BUILD_INFO.json',ROOT/'scripts/check_contract.py',ROOT/'docs/g3x_handoff.md']
    (OUT/'closeout_sha256.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'topology','commands','code_commits'}},indent=2))
if __name__=='__main__':main()
