"""Repeat only the required capacity experiment; immutable existing runtime image."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,subprocess,threading,time,uuid
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
commands=[];realms=[]
def run(args,timeout=600):
    print('RUN',subprocess.list2cmdline(args),flush=True)
    started=datetime.now(timezone.utc).isoformat();result=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=timeout)
    n=len(commands)+1
    (OUT/f'{n:03}_stdout.txt').write_bytes(result.stdout);(OUT/f'{n:03}_stderr.txt').write_bytes(result.stderr)
    commands.append({'command':args,'started_at':started,'exit_code':result.returncode})
    (OUT/'commands.json').write_text(json.dumps(commands,indent=2))
    print('EXIT',result.returncode,flush=True)
    if result.returncode:raise RuntimeError('command failed; raw output preserved')
    return result
def compose(project,*args):return run(['docker','compose','--project-name',project,*args])
def main():
    suffix=uuid.uuid4().hex[:8];code=json.loads((ROOT/'BUILD_INFO.json').read_text())['code_git_sha']
    image=run(['docker','image','inspect','orange-invest-g3x:local','--format','{{.Id}}']).stdout.decode().strip()
    compose('orange-invest','down')
    try:
        for count in [1,100]:
            project='orange-repeat-'+str(count)+'-'+suffix;realms.append(project)
            compose(project,'up','-d','--no-build','--wait')
            if count==1:compose(project,'stop','api2','worker2')
            identity=compose(project,'exec','-T','api','python','-c','from app.runtime.observe import build_sha; print(build_sha())').stdout.decode().strip()
            assert identity==code,(identity,code)
            services=['api','worker','pg','provider','telemetry','gateway']+(['api2','worker2'] if count==100 else [])
            sample=['docker','stats','--no-stream','--format','{{json .}}',*[project+'-'+s+'-1' for s in services]]
            metrics=[];stop=threading.Event()
            def monitor():
                while not stop.is_set():
                    r=subprocess.run(sample,cwd=ROOT,capture_output=True,timeout=10)
                    metrics.append({'utc':datetime.now(timezone.utc).isoformat(),'exit_code':r.returncode,'stdout':r.stdout.decode(errors='replace')})
                    stop.wait(1)
            thread=threading.Thread(target=monitor);thread.start();label='repeat_'+str(count)
            try:
                compose(project,'exec','-T','api','python','-X','utf8','scripts/g3x_load.py','--count',str(count),'--label',label,
                        '--base','http://api:8080' if count==1 else 'http://gateway:8080')
            finally:
                stop.set();thread.join(timeout=12)
                (OUT/('resources_'+str(count)+'.json')).write_text(json.dumps(metrics,indent=2))
                compose(project,'cp','api:/state/receipts/'+label,str(OUT/label))
            compose(project,'down')
        (OUT/'receipt.json').write_text(json.dumps({'status':'PASS','code_commit':code,'image_id':image,
            'purpose':'Second identical-code fresh-state 1/100 workflow and separate 100 duplicate-confirmation experiments. Backup and clean-worktree proof are in the first release receipt.',
            'commands':commands},indent=2)+'\n')
    finally:
        for project in realms:
            r=subprocess.run(['docker','compose','--project-name',project,'down'],cwd=ROOT,capture_output=True)
            (OUT/(project+'_cleanup.txt')).write_bytes(r.stdout+r.stderr)
        compose('orange-invest','up','-d','--no-build','--wait')
        (OUT/'sha256.json').write_text(json.dumps({p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()},indent=2)+'\n')
if __name__=='__main__':main()
