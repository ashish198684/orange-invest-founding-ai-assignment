"""Host-only evidence orchestration. Local Compose, fresh realms, no push/cloud.

Runs comparable isolated 1x/100x projects, native PG backup/restore and a clean
Git worktree's three primary startup/test/shutdown commands. Never removes volumes.
"""
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from threading import Event,Thread

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
    out=ROOT/'artifacts/receipts'/args.label;out.mkdir(exist_ok=False,parents=True)
    commands=[];serial=0
    def run(command,*,cwd=ROOT,expected=0,timeout=360):
        nonlocal serial
        serial+=1;start=datetime.now(timezone.utc).isoformat();t=time.monotonic()
        print('RUN',serial,subprocess.list2cmdline(command),flush=True)
        result=subprocess.run(command,cwd=cwd,capture_output=True,timeout=timeout)
        (out/f'{serial:03}_stdout.txt').write_bytes(result.stdout);(out/f'{serial:03}_stderr.txt').write_bytes(result.stderr)
        commands.append({'command':command,'cwd':str(cwd),'started_at':start,'elapsed_seconds':time.monotonic()-t,'exit_code':result.returncode})
        (out/'commands.json').write_text(json.dumps(commands,indent=2))
        print('EXIT',result.returncode,flush=True)
        if result.returncode!=expected:raise RuntimeError(f'command {serial} failed; preserved raw output')
        return result
    def compose(project,*command,cwd=ROOT):return run(['docker','compose','--project-name',project,*command],cwd=cwd)
    suffix=uuid.uuid4().hex[:8]
    run(['docker','info','--format','{{.NCPU}} CPUs; {{.MemTotal}} bytes; engine {{.ServerVersion}}'])
    run(['docker','compose','config'])
    # Existing synthetic development ledgers and volumes are retained, never reset.
    compose('orange-invest','down')
    realms=[]
    try:
        for count in [1,100]:
            project='orange-bench-'+str(count)+'-'+suffix;realms.append(project)
            compose(project,'up','-d','--build','--wait')
            if count==1:compose(project,'stop','api2','worker2')
            compose(project,'ps','--format','json')
            sample=['docker','stats','--no-stream','--format','{{json .}}',project+'-api-1',project+'-worker-1',project+'-pg-1']
            sample.extend([project+'-provider-1',project+'-telemetry-1',project+'-gateway-1'])
            if count==100:sample.extend([project+'-api2-1',project+'-worker2-1'])
            run(sample)
            label='load_'+str(count)
            measurements=[];stop=Event()
            def monitor():
                while not stop.is_set():
                    result=subprocess.run(sample,capture_output=True,timeout=10)
                    measurements.append({'utc':datetime.now(timezone.utc).isoformat(),'exit_code':result.returncode,
                                         'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')})
                    stop.wait(1)
            thread=Thread(target=monitor);thread.start()
            try:
                compose(project,'exec','-T','api','python','-X','utf8','scripts/g3x_load.py','--count',str(count),'--label',label,
                        '--base','http://api:8080' if count==1 else 'http://gateway:8080')
            finally:
                stop.set();thread.join(timeout=12)
                (out/('resources_'+str(count)+'.json')).write_text(json.dumps(measurements,indent=2))
                compose(project,'cp','api:/state/receipts/'+label,str(out/label))
            run(sample)
            if count==100:
                restore_label='restore'
                compose(project,'exec','-T','api','python','-X','utf8','scripts/g3x_restore.py','--prepare','--label',restore_label)
                database='orange_rehearsal_'+suffix
                compose(project,'exec','-T','pg','pg_dump','-U','postgres','-d','orange','-Fc','-f','/tmp/orange_rehearsal.dump')
                compose(project,'cp','pg:/tmp/orange_rehearsal.dump',str(out/'synthetic_pg_backup.dump'))
                compose(project,'exec','-T','pg','createdb','-U','postgres',database)
                compose(project,'exec','-T','pg','pg_restore','-U','postgres','-d',database,'--no-owner','/tmp/orange_rehearsal.dump')
                compose(project,'exec','-T','api','python','-X','utf8','scripts/g3x_restore.py','--database',database,'--label',restore_label)
                rollback_db='orange_rehearsal_rollback_'+suffix
                compose(project,'exec','-T','pg','createdb','-U','postgres',rollback_db)
                compose(project,'exec','-T','api','python','-X','utf8','scripts/g3x_restore.py','--rollback','--database',rollback_db,'--label',restore_label)
                compose(project,'exec','-T','pg','dropdb','-U','postgres',rollback_db)
                compose(project,'cp','api:/state/receipts/'+restore_label,str(out/'restore'))
                # Drop ONLY the exact disposable DB created above; original orange remains.
                assert database.startswith('orange_rehearsal_') and len(suffix)==8
                compose(project,'exec','-T','pg','dropdb','-U','postgres',database)
            compose(project,'down')
        head=run(['git','rev-parse','HEAD']).stdout.decode().strip()
        clean=ROOT.parent/('orange-g3x-clean-'+suffix)
        run(['git','worktree','add','--detach',str(clean),head])
        project='orange-proof-'+suffix;realms.append(project)
        # These are the exact three essential clean-checkout commands. Artifact
        # collection is evidence handling, not an additional setup prerequisite.
        compose(project,'up','-d','--build','--wait',cwd=clean)
        compose(project,'exec','-T','api','python','-X','utf8','scripts/g3x_checks.py','--label','clean_source',cwd=clean)
        compose(project,'cp','api:/state/receipts/clean_source',str(out/'clean_source'),cwd=clean)
        compose(project,'down',cwd=clean)
        report={'code_commit':head,'clean_worktree':str(clean),'isolated_projects':realms,
                'status':'PASS','claims_boundary':'1x versus 100 active workflows; separate 100 duplicate confirmations. Not 100x throughput or production HA. G4/G5 not started.',
                'commands':commands}
        (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:
        # Idempotent, non-destructive shutdown of only our named proof realms.
        for project in realms:
            result=subprocess.run(['docker','compose','--project-name',project,'down'],cwd=ROOT,capture_output=True)
            (out/(project+'_cleanup.txt')).write_bytes(result.stdout+result.stderr)
        # Restore the development topology; all prior synthetic data volumes persist.
        run(['docker','compose','up','-d','--build','--wait'])
        (out/'sha256.json').write_text(json.dumps({p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                                for p in out.rglob('*') if p.is_file()},indent=2)+'\n')

if __name__=='__main__':main()
