"""Assemble attributable bug deltas and final integrity; never rerun or edit history."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
RECEIPTS=ROOT/'artifacts/receipts'
G1='32e707cdb0c4fb509455e0d2525f196e756d49ac'
G2='3d79a207bffd3bda1505333e3c7804bf00e657ae'
sha=lambda b:hashlib.sha256(b).hexdigest()

def write(p,v): p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def from_zip(label,name):
    with zipfile.ZipFile(RECEIPTS/(label+'_source.zip')) as z:
        return z.read(name)

assert not (OUT/'final_integrity.json').exists(), 'Refuse overwrite'
bugs=[
 ('g1_wal_transaction','g1_first_run','g1_after_wal_fix','app/storage.py',G1),
 ('g1_insert_counts','g1_after_wal_fix','g1_after_outcome_fix','app/provider_mock/tools.py',G1),
 ('g1_forbidden_403','g1_after_outcome_fix','g1_final','app/provider_mock/tools.py',G1),
 ('g2_operation_columns','g2_first_implementation_20261102','g2_after_sql_connection_fix_20261102','app/workflow.py',G2),
 ('g2_retry_transition','g2_after_sql_connection_fix_20261102','g2_after_retry_transition_fix_20261102','app/workflow.py',G2),
 ('g2_wrong_slot_readback','g2_adversarial_readback_red_20261102',None,'app/workflow.py',G2),
]
records=[]
for name,red,fix,source,commit in bugs:
    before=from_zip(red,source)
    after=from_zip(fix,source) if fix else subprocess.check_output(['git','show',f'{commit}:{source}'],cwd=ROOT)
    patch=''.join(difflib.unified_diff(before.decode('utf-8').splitlines(True),after.decode('utf-8').splitlines(True),
                  fromfile=red+'/'+source,tofile=(fix or commit)+'/'+source))
    assert patch, name+' has no observed delta'
    (OUT/(name+'.patch')).write_text(patch,encoding='utf-8')
    records.append(dict(bug=name,red_receipt=red+'.txt',red_snapshot=red+'_source.zip',source_file=source,
        fix_snapshot=fix+'_source.zip' if fix else None,red_source_sha256=sha(before),
        fix_source_sha256=sha(after),final_implementation_commit=commit,
        green_regression_receipt='p1_postcommit_20261101/receipt.json' if name.startswith('g1_') else 'g2_postcommit_20261102/receipt.json',
        delta_scope='Full actual source delta between recorded revisions; may include adjacent changes, not an invented surgical patch'))
write(OUT/'bug_provenance.json',records)
source_diff=subprocess.check_output(['git','diff','4685c4abc1481a58daec61ea40e467b0f6408788',G2,'--',
    '.gitignore','DECISIONS.md','README.md','app','tests','scripts','docs/actual_progress.md',
    'docs/g2_handoff.md','docs/g2_acceptance_matrix.md'],cwd=ROOT)
(OUT/'g2_source_diff.patch').write_bytes(source_diff)
pre=json.loads((RECEIPTS/'p1_preflight_20261101.json').read_text())
hashes=dict(pre['historical_evidence_sha256'])
for label in ['p1_postcommit_20261101','g2_candidate_20261102','g2_postcommit_20261102']:
    hashes.update(json.loads((RECEIPTS/label/'sha256.json').read_text()))
violations=[p for p,h in hashes.items() if not (ROOT/p).is_file() or sha((ROOT/p).read_bytes())!=h]
assert not violations,violations
receipt=json.loads((RECEIPTS/'g2_postcommit_20261102/receipt.json').read_text())
assert receipt['objective_status']=='PASS' and receipt['source_matches_commit']
source_violations=[]
for name,h in receipt['source_sha256'].items():
    blob=subprocess.check_output(['git','show',f'{G2}:{name}'],cwd=ROOT)
    if sha(blob)!=h or sha((ROOT/name).read_bytes())!=h: source_violations.append(name)
assert not source_violations,source_violations
inspection=json.loads((RECEIPTS/'g2_postcommit_20261102/independent_db_checks.json').read_text())
assert inspection['checked']==inspection['passed']==38
probe=json.loads((RECEIPTS/'g2_postcommit_20261102/timeout_probe/database.json').read_text())
summary=dict(order='ORANGE-CTO-20261101-P1-G2-001',G1_source_commit=G1,G2_source_commit=G2,
    exact_evidence_files_verified=len(hashes),evidence_hash_violations=violations,
    committed_source_hash_violations=source_violations,tests_passed=receipt['passed'],
    tests_run=receipt['tests_run'],failures=receipt['failures'],errors=receipt['errors'],skipped=receipt['skipped'],
    independently_inspected_databases=inspection['checked'],independent_database_violations=0,
    timeout_booking=probe['provider_bookings'][0],timeout_operation=probe['operations'][0],
    canonical_sha256=sha((ROOT/'CANONICAL.md').read_bytes()),
    assessment='G1 and G2 objective checks PASS; formal CTO acceptance pending. Submission NO-GO. STOP after G2.',
    unresolved_test_failures=[],G3='NOT_STARTED',G4='NOT_STARTED',G5='NOT_STARTED',Groq='NOT_IMPLEMENTED')
write(OUT/'final_integrity.json',summary)
write(OUT/'sha256.json',{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in OUT.iterdir() if p.is_file()})
print(json.dumps(summary,indent=2))
