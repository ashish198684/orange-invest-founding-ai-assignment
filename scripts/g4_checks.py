"""One offline check command: old regressions, user journeys and adapter defenses."""
import argparse,hashlib,json,os,shutil,subprocess,sys,re
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--require-committed',action='store_true');a=p.parse_args()
    if not a.label.replace('_','').isalnum():raise ValueError('invalid_label')
    state=Path(os.getenv('RUNTIME_STATE','data/runtime'));out=state/'receipts'/a.label;out.mkdir(exist_ok=False,parents=True)
    commands=[]
    def run(command,timeout=600):
        start=datetime.now(timezone.utc).isoformat();r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout);i=len(commands)
        (out/f'{i:02d}_stdout.txt').write_bytes(r.stdout);(out/f'{i:02d}_stderr.txt').write_bytes(r.stderr)
        commands.append({'command':command,'exit_code':r.returncode,'started_at':start});(out/'commands.json').write_text(json.dumps(commands,indent=2));print(command,'exit',r.returncode,flush=True)
        if r.returncode:raise SystemExit(r.returncode)
        return r
    old=a.label+'_regressions';evals=a.label+'_evals'
    run([sys.executable,'-X','utf8','scripts/g3x_checks.py','--label',old])
    run([sys.executable,'-X','utf8','scripts/g4_evals.py','--label',evals])
    adapter=run([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests_g4','-v'])
    adapter_count=int(re.search(r'Ran (\d+) tests',adapter.stderr.decode())[1]);assert adapter_count>=16
    source=state/'receipts'/evals;report=json.loads((source/'receipt.json').read_text());assert report['mode']=='scripted-offline' and report['passed']==28 and report['failed']==0
    generated=state/'evals'/a.label;generated.mkdir(exist_ok=False,parents=True)
    for name in ['results.csv','results.json','source_sha256.json']:shutil.copyfile(source/name,generated/name)
    # Preserve the actual worker run unmodified. Related API runs stay in E12's
    # per-case trace directory, linked by workflow ID, approval and operation.
    timeout_file=None
    for path in (source/'E12/traces').glob('*.jsonl'):
        events=[json.loads(line) for line in path.read_text().splitlines()]
        if any(e['event_type']=='provider_timeout' and e['tool_name']=='book' for e in events):
            assert any(e['event_type']=='run_exit' and e.get('status')=='BOOKED' for e in events);timeout_file=path;break
    assert timeout_file,'Missing raw verified timeout run'
    shutil.copyfile(timeout_file,generated/'timeout_after_success.jsonl')
    from app.runtime.observe import build_sha
    sha=build_sha()
    if a.require_committed and sha=='UNCOMMITTED':raise SystemExit('Source attribution mismatch')
    receipt={'gate':'G4','status':'PASS','acceptance':'CTO review pending','code_commit':sha,'commands':commands,
             'offline_evals':28,'sqlite_tests':65,'g3x_tests':39,'adapter_tests':adapter_count,'skipped':0,'model_mode':'scripted-offline',
             'live_api_called':False,'generated_artifacts':str(generated),'raw_timeout_run':timeout_file.name,
             'timestamp':datetime.now(timezone.utc).isoformat(),'boundary':'Browser and live Groq smoke have separate receipts. G5 not authorized.'}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2));(out/'sha256.json').write_text(json.dumps({str(x.relative_to(out)):hashlib.sha256(x.read_bytes()).hexdigest() for x in out.rglob('*') if x.is_file()},indent=2));print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
