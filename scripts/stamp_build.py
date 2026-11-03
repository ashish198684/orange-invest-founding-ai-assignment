"""Bind runtime bytes to a committed source tree; never include secret files."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    paths=[*ROOT.glob('app/**/*.py'),*ROOT.glob('app/web/*'),*ROOT.glob('scripts/*.py'),*ROOT.glob('tests/**/*.py'),*ROOT.glob('tests_g3x/**/*.py'),*ROOT.glob('tests_g4/**/*.py')]
    paths += [ROOT/x for x in ['compose.yaml','Dockerfile','requirements.txt','requirements-g3x.txt','.dockerignore','.gitignore','.gitattributes']]
    paths=[p for p in paths if p.is_file() and p.name!='check_contract.py']
    hashes={}
    for path in sorted(paths):
        name=path.relative_to(ROOT).as_posix();raw=path.read_bytes()
        committed=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
        if raw!=committed:raise SystemExit('Source differs from committed bytes: '+name)
        hashes[name]=hashlib.sha256(raw).hexdigest()
    data={'code_git_sha':head,'source_sha256':hashes,'excluded_governance':'Canonical and check_contract.py are independently pinned; BUILD_INFO, documentation and generated evidence do not change runtime behavior.'}
    (ROOT/'BUILD_INFO.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({'code_git_sha':head,'files':len(hashes)}))
if __name__=='__main__':main()
