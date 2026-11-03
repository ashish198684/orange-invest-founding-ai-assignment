"""Host orchestration with exact exits and durable raw logs; no secret output."""
import argparse,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('action',choices=['build','evals','offline','regressions','browser','fresh','adapter','live']);p.add_argument('--user');p.add_argument('--match');p.add_argument('--live-browser',action='store_true');a=p.parse_args()
    out=ROOT/'artifacts/receipts'/a.label;out.mkdir(exist_ok=False,parents=True);commands=[]
    def run(cmd,timeout=600):
        print('RUN',subprocess.list2cmdline(cmd),flush=True);start=time.monotonic();r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=timeout)
        i=len(commands);(out/f'{i:02d}_stdout.txt').write_bytes(r.stdout);(out/f'{i:02d}_stderr.txt').write_bytes(r.stderr)
        commands.append({'command':cmd,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-start,'timestamp':datetime.now(timezone.utc).isoformat()});(out/'commands.json').write_text(json.dumps(commands,indent=2));print('EXIT',r.returncode,flush=True);return r.returncode
    prefix=['docker','compose']
    if a.action=='fresh':
        project='orange-g4-'+a.label.lower().replace('_','-')[-40:]
        code=run(prefix+['down']);fresh=prefix+['--project-name',project]
        try:
            if not code:code=run(fresh+['up','-d','--build','--wait'])
            label=a.label+'_regressions'
            if not code:code=run(fresh+['exec','-T','api','python','-X','utf8','scripts/g3x_checks.py','--label',label])
            run(fresh+['cp','api:/state/receipts/'+label,str(out/'regressions')])
            label=a.label+'_evals'
            if not code:code=run(fresh+['exec','-T','api','python','-X','utf8','scripts/g4_evals.py','--label',label])
            run(fresh+['cp','api:/state/receipts/'+label,str(out/'cases')])
        finally:
            run(fresh+['down']);run(prefix+['up','-d','--wait'])
    elif a.action=='build':code=run(prefix+['up','-d','--build','--wait'])
    elif a.action in {'evals','offline'}:
        code=0
        for file in ['scripts/g4_fixture.py','scripts/g4_evals.py','app/runtime/http_api.py','app/runtime/observe.py']:
            code=run(prefix+['cp',file,'api:/orange/'+file])
            if code:break
        label=a.label+'_cases'
        if not code:code=run(prefix+['exec','-T','api','python','-X','utf8','scripts/g4_evals.py','--label',label]+(['--match',a.match] if a.match else []))
        run(prefix+['cp','api:/state/receipts/'+label,str(out/'cases')])
        if a.action=='offline' and not code:
            label=a.label+'_regressions';code=run(prefix+['exec','-T','api','python','-X','utf8','scripts/g3x_checks.py','--label',label])
            run(prefix+['cp','api:/state/receipts/'+label,str(out/'regressions')])
    elif a.action=='adapter':
        code=run(prefix+['exec','-T','api','python','-X','utf8','-m','unittest','discover','-s','tests_g4','-v'])
    elif a.action=='live':
        label=a.label+'_cases';code=run(prefix+['exec','-T','api','python','-X','utf8','scripts/g4_live_smoke.py','--label',label])
        run(prefix+['cp','api:/state/receipts/'+label,str(out/'cases')])
    elif a.action=='regressions':
        label=a.label+'_cases';code=run(prefix+['exec','-T','api','python','-X','utf8','scripts/g3x_checks.py','--label',label]);run(prefix+['cp','api:/state/receipts/'+label,str(out/'cases')])
    else:
        uid=a.user or a.label
        code=run(prefix+['cp','scripts/g4_fixture.py','api:/orange/scripts/g4_fixture.py'])
        if not code:code=run(prefix+['exec','-T','api','python','-X','utf8','scripts/g4_fixture.py','--user',uid])
        if not code:code=run([sys.executable,'-X','utf8','scripts/g4_browser.py','--label',a.label+'_screens','--user',uid]+(['--live'] if a.live_browser else []))
    raise SystemExit(code)
if __name__=='__main__':main()
