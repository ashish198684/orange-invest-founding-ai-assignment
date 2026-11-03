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
    parser.add_argument('--gate',choices=['G3X','G4'],default='G3X')
    parser.add_argument('--g4-status',choices=['RUNNING','ENGINEERING_PASS','FAIL'],default='RUNNING')
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
    boundary=('G4 only under sponsor-dispatched Section P4; CTO acceptance pending. G5, push and submission remain unauthorized.' if args.gate=='G4' else 'G3X only; formal CTO adjudication pending. G4/G5/Groq are not authorized.')
    entry=f"\n### {args.gate} execution record {datetime.now(timezone.utc).isoformat()}\n\n- **Evidence:** `{receipt.relative_to(ROOT).as_posix()}`, SHA-256 `{sha(receipt.read_bytes())}`.\n- **Observed:** {args.summary}\n- **Source attribution:** `{payload.get('code_commit',payload.get('source_commit','see hashed source snapshot'))}`.\n- **Prior canonical SHA-256:** `{old}`; archived unchanged at `{archive.relative_to(ROOT).as_posix()}`. Required contract pins remain; the verifier additionally checks this preserved execution revision.\n- **Gate boundary:** {boundary}\n"
    current=before
    if args.gate=='G4':
        current=current.replace(b'G4 PREPARED BUT NOT DISPATCHED',b'G4 SPONSOR-DISPATCHED / RUNNING',1)
        current=current.replace(b'Section P4 prepares the NEXT manually dispatched G4 gate, governed by',b'Section P4 governs the sponsor-manually-dispatched G4 gate, governed by',1)
        current=current.replace(b'**Date:** 2026-11-02',b'**Date:** 2026-11-03',1)
        if args.g4_status=='ENGINEERING_PASS':current=current.replace(b'G4 SPONSOR-DISPATCHED / RUNNING',b'G4 ENGINEERING PASS / CTO ACCEPTANCE PENDING',1)
        elif args.g4_status=='FAIL':current=current.replace(b'G4 SPONSOR-DISPATCHED / RUNNING',b'G4 FAIL / CTO REVIEW REQUIRED',1)
    updated=current+(heading+entry).encode('utf-8');new=sha(updated)
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
