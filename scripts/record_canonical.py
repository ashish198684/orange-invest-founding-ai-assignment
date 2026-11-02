"""Append sponsor-authorized evidence to the one master; preserve prior bytes/pin."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--receipt',required=True);parser.add_argument('--summary',required=True)
    args=parser.parse_args();receipt=(ROOT/args.receipt).resolve()
    if ROOT not in receipt.parents or not receipt.is_file():raise ValueError('receipt must exist inside repository')
    payload=json.loads(receipt.read_text(encoding='utf-8'))
    canonical=ROOT/'CANONICAL.md';verifier=ROOT/'scripts/check_contract.py'
    before=canonical.read_bytes();old=sha(before)
    source=verifier.read_text(encoding='utf-8')
    match=re.search(r"'CANONICAL.md': '([a-f0-9]{64})'",source)
    if not match or match[1]!=old:raise SystemExit('STOP: current canonical does not match its prior pin')
    archive=ROOT/'docs/canonical_history'/('CANONICAL_EXECUTION_'+old+'_FROZEN.md')
    if archive.exists() and archive.read_bytes()!=before:raise SystemExit('STOP: historical archive mismatch')
    archive.write_bytes(before)
    heading='' if b'## N. Verified execution journal' in before else '\n\n## N. Verified execution journal\n\nThis journal records executed evidence under the sponsor-authorized update policy. It does not expand L4/M2-M4 scope. Prior complete master revisions are byte-preserved as historical archives, never competing masters.\n'
    entry=f"\n### Execution record {datetime.now(timezone.utc).isoformat()}\n\n- **Evidence:** `{receipt.relative_to(ROOT).as_posix()}`, SHA-256 `{sha(receipt.read_bytes())}`.\n- **Observed:** {args.summary}\n- **Source attribution:** `{payload.get('code_commit',payload.get('source_commit','see hashed source snapshot'))}`.\n- **Prior canonical SHA-256:** `{old}`; archived unchanged at `{archive.relative_to(ROOT).as_posix()}`. Required contract pins remain; the verifier additionally checks this preserved execution revision.\n- **Gate boundary:** G3X only; formal CTO adjudication pending. G4/G5/Groq are not authorized.\n"
    updated=before+(heading+entry).encode('utf-8');new=sha(updated)
    source=source.replace("'CANONICAL.md': '"+old+"'","'CANONICAL.md': '"+new+"'",1)
    archive_rel=archive.relative_to(ROOT).as_posix()
    line="    '"+archive_rel+"': '"+old+"',\n"
    if archive_rel not in source:source=source.replace("EXPECTED = {\n","EXPECTED = {\n"+line,1)
    canonical.write_bytes(updated);verifier.write_text(source,encoding='utf-8',newline='\n')
    run=subprocess.run([sys.executable,'-X','utf8','scripts/check_contract.py'],cwd=ROOT,capture_output=True)
    out=receipt.parent/('canonical_update_'+new[:12]+'.json')
    record={'prior_sha256':old,'current_sha256':new,'archive':archive_rel,'receipt_sha256':sha(receipt.read_bytes()),
            'command':[sys.executable,'-X','utf8','scripts/check_contract.py'],'exit_code':run.returncode,
            'check_output':json.loads(run.stdout)}
    out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))
    raise SystemExit(run.returncode)
if __name__=='__main__':main()
