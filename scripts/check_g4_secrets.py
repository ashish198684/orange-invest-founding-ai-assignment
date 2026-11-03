"""Scan selected source/evidence for the actual ignored key without printing it."""
import argparse,json,re,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();out=ROOT/a.out
    env=(ROOT/'.env').read_text(encoding='utf-8-sig');match=re.search(r'^\s*(?:export\s+)?GROQ_API_KEY\s*=\s*(.+?)\s*$',env,re.M)
    if not match:raise SystemExit('Key configuration missing; no value printed')
    key=match[1].strip().strip('\"\'').encode();assert len(key)>16
    paths=[ROOT/x for x in subprocess.check_output(['git','ls-files'],cwd=ROOT).decode().splitlines()]
    paths += [x for x in (ROOT/'artifacts/receipts').glob('g4*/**/*') if x.is_file()]
    paths += [x for folder in [ROOT/'app',ROOT/'scripts',ROOT/'tests_g4',ROOT/'artifacts/evals',ROOT/'artifacts/traces'] for x in folder.rglob('*') if x.is_file() and '__pycache__' not in x.parts]
    failures=[];count=0
    for path in set(paths):
        if not path.is_file() or path==ROOT/'.env':continue
        count+=1
        if key in path.read_bytes():failures.append(path.relative_to(ROOT).as_posix())
        if path.suffix=='.zip':
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if key in z.read(name):failures.append(path.relative_to(ROOT).as_posix()+':'+name)
    tracked=subprocess.run(['git','ls-files','--error-unmatch','.env'],cwd=ROOT,capture_output=True).returncode==0
    report={'status':'PASS' if not failures and not tracked else 'FAIL','actual_key_printed':False,'files_scanned':count,'leaking_paths':failures,'env_tracked':tracked};out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(report,indent=2));print(json.dumps(report));raise SystemExit(0 if report['status']=='PASS' else 1)
if __name__=='__main__':main()
