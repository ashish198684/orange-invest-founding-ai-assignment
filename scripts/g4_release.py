"""G4 only: clean-checkout offline proof, real Groq/browser replay and SQL audit.

All local volumes are preserved. No push, cloud deployment, G5 video or submission.
"""
import argparse,hashlib,json,re,shutil,subprocess,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);a=p.parse_args()
    if not a.label.replace('_','').isalnum():raise ValueError('invalid_label')
    out=ROOT/'artifacts/receipts'/a.label;out.mkdir(exist_ok=False,parents=True);commands=[]
    def run(cmd,*,cwd=ROOT,timeout=900,required=True):
        print('RUN',subprocess.list2cmdline(cmd),flush=True);start=time.monotonic();r=subprocess.run(cmd,cwd=cwd,capture_output=True,timeout=timeout);i=len(commands)
        (out/f'{i:02d}_stdout.txt').write_bytes(r.stdout);(out/f'{i:02d}_stderr.txt').write_bytes(r.stderr)
        commands.append({'command':cmd,'cwd':str(cwd),'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-start,'timestamp':datetime.now(timezone.utc).isoformat()});(out/'commands.json').write_text(json.dumps(commands,indent=2));print('EXIT',r.returncode,flush=True)
        if required and r.returncode:raise RuntimeError('Failed command '+str(i)+'; raw evidence retained')
        return r
    head=run(['git','rev-parse','HEAD']).stdout.decode().strip();source=json.loads((ROOT/'BUILD_INFO.json').read_text())['code_git_sha'];suffix=uuid.uuid4().hex[:8]
    project='orange-g4-proof-'+suffix;demo='orange-g4-demo-'+source[:8];clean=ROOT.parent/('orange-g4-clean-'+suffix)
    prefix=['docker','compose'];fresh=prefix+['--project-name',project];live=prefix+['--project-name',demo]
    active=ROOT/'data/g4_demo_project.txt';report={'gate':'G4','status':'FAIL','code_commit':source,'checkout_commit':head,'clean_worktree':str(clean),'proof_project':project,'demo_project':demo,'commands':commands,'stopped':'G4 only; G5 not started'}
    demo_started=False
    try:
        if active.exists():
            old=active.read_text().strip()
            if not re.fullmatch(r'orange-g4-demo-[a-f0-9]{8}',old):raise ValueError('unexpected_demo_project')
            run(prefix+['--project-name',old,'down'])
        run(prefix+['down'])
        run(['git','worktree','add','--detach',str(clean),head])
        assert not (clean/'.env').exists(),'Secret file must not be in clean checkout'
        # The three primary clean-checkout commands; copies are evidence handling.
        run(fresh+['up','-d','--build','--wait'],cwd=clean)
        label=a.label+'_clean'
        try:run(fresh+['exec','-T','api','python','-X','utf8','scripts/g4_checks.py','--label',label,'--require-committed'],cwd=clean)
        finally:
            for remote,name in [('receipts/'+label,'offline'),('receipts/'+label+'_regressions','regressions'),('receipts/'+label+'_evals','evals'),('evals/'+label,'generated')]:
                run(fresh+['cp','api:/state/'+remote,str(out/name)],cwd=clean,required=False)
        run(fresh+['down'],cwd=clean)
        # A fresh, explicitly named demo realm. Previous development/test ledgers
        # remain preserved in their volumes; ordinary startup never resets them.
        run(live+['up','-d','--wait']);demo_started=True;active.parent.mkdir(exist_ok=True);active.write_text(demo)
        live_label=a.label+'_live'
        try:run(live+['exec','-T','api','python','-X','utf8','scripts/g4_live_smoke.py','--label',live_label])
        finally:run(live+['cp','api:/state/receipts/'+live_label,str(out/'live')],required=False)
        uid='browser-'+suffix;browser_label=a.label+'_browser'
        run(live+['exec','-T','api','python','-X','utf8','scripts/g4_fixture.py','--user',uid])
        try:run([sys.executable,'-X','utf8','scripts/g4_browser.py','--label',browser_label,'--user',uid,'--live'])
        finally:
            folder=ROOT/'artifacts/receipts'/browser_label
            if folder.exists():shutil.copytree(folder,out/'browser')
        audit_label=a.label+'_audit'
        try:run(live+['exec','-T','api','python','-X','utf8','scripts/g4_audit.py','--live-label',live_label,'--browser-user',uid,'--label',audit_label])
        finally:run(live+['cp','api:/state/receipts/'+audit_label,str(out/'audit')],required=False)
        offline=json.loads((out/'offline/receipt.json').read_text());actual_live=json.loads((out/'live/receipt.json').read_text());browser=json.loads((out/'browser/receipt.json').read_text());audit=json.loads((out/'audit/receipt.json').read_text())
        assert all(x['status']=='PASS' for x in [offline,actual_live,browser,audit]);assert offline['code_commit']==source==actual_live['code_commit']==audit['code_commit']
        generated=ROOT/'artifacts/evals';generated.mkdir(exist_ok=True,parents=True)
        for name in ['results.csv','results.json','source_sha256.json']:shutil.copyfile(out/'generated'/name,generated/name)
        raw=ROOT/'artifacts/traces';raw.mkdir(exist_ok=True,parents=True);shutil.copyfile(out/'generated/timeout_after_success.jsonl',raw/'timeout_after_success.jsonl')
        report.update(status='PASS',tests={k:offline[k] for k in ['sqlite_tests','g3x_tests','offline_evals','adapter_tests','skipped']},live_model_turns=actual_live['model_turns'],browser_checks=browser['checks'],audit=audit,app_url='http://127.0.0.1:8080/',acceptance='CTO inspection pending; stopped at G4',g5='NOT STARTED',submission='NO-GO')
    except Exception as exc:
        report['error']=str(exc)
    finally:
        run(fresh+['down'],cwd=clean if clean.exists() else ROOT,required=False)
        if not demo_started:run(prefix+['up','-d','--wait'],required=False)
        (out/'receipt.json').write_text(json.dumps(report,indent=2));(out/'sha256.json').write_text(json.dumps({x.relative_to(out).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in out.rglob('*') if x.is_file() and x.name!='sha256.json'},indent=2));print(json.dumps({k:report.get(k) for k in ['status','error','code_commit','app_url','demo_project','tests']},indent=2))
    raise SystemExit(0 if report['status']=='PASS' else 1)
if __name__=='__main__':main()
