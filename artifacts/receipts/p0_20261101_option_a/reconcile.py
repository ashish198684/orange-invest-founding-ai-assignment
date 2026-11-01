"""P0-only reconciliation and preservation receipt; no application execution."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
EXPECTED = '2f057c7a626174dde3cc35c04a6c4082f2b55e8f49e2b92d2bda43703895b5e2'
ARCHIVE = ROOT / 'docs/proposals/20261101_cto_addendum_NOT_AUTHORITATIVE_NOT_APPROVED'
sha = lambda b: hashlib.sha256(b).hexdigest()

def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def inventory():
    return {p.relative_to(ROOT).as_posix(): sha(p.read_bytes())
            for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

canonical = ROOT / 'CANONICAL.md'
decisions = ROOT / 'DECISIONS.md'
original = canonical.read_bytes()
baseline = git('show', 'd63a1d8:CANONICAL.md')
decision_before = decisions.read_bytes()
assert sha(baseline) == EXPECTED, 'STOP: baseline differs from pinned source hash'
assert original.startswith(baseline), 'STOP: unexplained changes before addendum'
suffix = original[len(baseline):]
assert suffix.startswith(b'\n---\n\n## CTO ADDENDUM `ORANGE-20261101-G1-AUDIT-G2-ORDER`'), 'STOP: unexpected suffix'
assert len(suffix.splitlines()) == 48, 'STOP: expected boundary newline plus 47 added lines'
assert b'## ADR-004' in decision_before and b'## ADR-005' in decision_before
assert b'## ADR-006' not in decision_before, 'STOP: ADR ID already exists'
assert not ARCHIVE.exists(), 'STOP: archive already exists'
assert not (OUT / 'receipt.json').exists(), 'STOP: receipt already exists'
before = inventory()
save_json(OUT / 'preservation_before.json', before)
(OUT / 'git_status_before.txt').write_bytes(git('status', '--short'))
(OUT / 'canonical_diff_before.patch').write_bytes(git('diff', 'd63a1d8', '--', 'CANONICAL.md'))
ARCHIVE.mkdir(parents=True)
(ARCHIVE / 'addendum_unchanged.md').write_bytes(suffix)
(ARCHIVE / 'CANONICAL_before_P0.md').write_bytes(original)
(ARCHIVE / 'README.md').write_text(
    '# NOT AUTHORITATIVE / NOT APPROVED\n\n'
    'Archival proposal only. The sponsor authorized Option A in P0: the original '
    'hash-verified CANONICAL.md governs. Nothing in this archive dispatches engineering.\n\n'
    '`addendum_unchanged.md` preserves the exact appended bytes, including the boundary '
    'newline. The original addendum describes itself as approved; that historical text '
    'is preserved unchanged and does not confer present authority.\n\n'
    '`CANONICAL_before_P0.md` preserves the complete pre-reconciliation working file.\n',
    encoding='utf-8')
canonical.write_bytes(baseline)
adr = '''
## ADR-006 / 2026-11-01 - P0 canonical reconciliation, Option A (v1)
- **Status / authority:** Accepted sponsor-dispatched P0 resolution only. Original employer PDF and hash-verified canonical remain authoritative; ADR-004 human-led dispatch and ADR-005 Groq selection are preserved.
- **Finding:** Git baseline d63a1d8 CANONICAL.md is an exact byte prefix of the pre-P0 working file. The only additional content is the boundary newline and 47-line CTO addendum; no other formatting or content differences were found. Baseline SHA-256 matches the existing pinned value.
- **Resolution:** Restore only CANONICAL.md to exact baseline bytes (LF, no final newline), SHA-256 2f057c7a626174dde3cc35c04a6c4082f2b55e8f49e2b92d2bda43703895b5e2. No pinned source hash is changed and no repository reset is performed.
- **Preservation:** docs/proposals/20261101_cto_addendum_NOT_AUTHORITATIVE_NOT_APPROVED/addendum_unchanged.md preserves the complete appended bytes unchanged; its README explicitly marks the proposal NOT AUTHORITATIVE / NOT APPROVED. CANONICAL_before_P0.md preserves the full pre-P0 working file, SHA-256 a5187084ff50451cc7813dcdb8a2310cdaecac0e0959d27632509278ed37d325. Historical approval language in the archived text does not grant current authority.
- **Verification / evidence:** Run the unchanged scripts/check_contract.py under the existing Python 3.12 interpreter. Exact command, actual stdout/stderr, exit code, before/after Git status, canonical diffs, preservation inventories and evidence hashes are recorded in artifacts/receipts/p0_20261101_option_a/. The generated receipt, rather than this ADR, establishes the check result.
- **Scope:** No application code, tests, historical receipts, source snapshots, AGENTS.md or assignment PDF changed. No G1 closeout, G2 work, Groq integration or onward phase authorized. Stop after P0 for CTO review.
'''
with decisions.open('ab') as handle:
    handle.write(adr.encode('utf-8'))
assert decisions.read_bytes().startswith(decision_before)
assert canonical.read_bytes() == baseline
assert (ARCHIVE / 'addendum_unchanged.md').read_bytes() == suffix
command = [sys.executable, '-X', 'utf8', 'scripts/check_contract.py']
run = subprocess.run(command, cwd=ROOT, capture_output=True)
(OUT / 'g0_stdout.json').write_bytes(run.stdout)
(OUT / 'g0_stderr.txt').write_bytes(run.stderr)
(OUT / 'canonical_diff_after.patch').write_bytes(git('diff', 'd63a1d8', '--', 'CANONICAL.md'))
restoration_diff = ''.join(difflib.unified_diff(original.decode('utf-8').splitlines(True), baseline.decode('utf-8').splitlines(True), fromfile='CANONICAL.before-P0.md', tofile='CANONICAL.md'))
(OUT / 'canonical_restoration.patch').write_text(restoration_diff, encoding='utf-8')
(OUT / 'decisions_added.patch').write_text(''.join(difflib.unified_diff(decision_before.decode('utf-8').splitlines(True), decisions.read_text(encoding='utf-8').splitlines(True), fromfile='DECISIONS.before-P0.md', tofile='DECISIONS.md')), encoding='utf-8')
after = inventory()
violations = [name for name, digest in before.items() if name not in {'CANONICAL.md', 'DECISIONS.md'} and after.get(name) != digest]
save_json(OUT / 'preservation_after.json', after)
(OUT / 'git_status_after.txt').write_bytes(git('status', '--short'))
receipt = {'phase': 'P0 only', 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
           'baseline_commit': git('rev-parse', 'd63a1d8').decode().strip(),
           'command_argv': command, 'command_powershell': '& "' + sys.executable + '" -X utf8 scripts/check_contract.py',
           'cwd': str(ROOT), 'exit_code': run.returncode, 'g0': json.loads(run.stdout),
           'canonical_before_sha256': sha(original), 'canonical_after_sha256': sha(baseline),
           'exact_byte_prefix': True, 'addendum_lines': 47, 'boundary_newline_preserved': True,
           'addendum_sha256': sha(suffix), 'decisions_sha256': sha(decisions.read_bytes()),
           'existing_files_checked': len(before), 'preservation_violations': violations,
           'archive': str(ARCHIVE), 'unresolved_discrepancies': violations,
           'commit': 'NOT_COMMITTED', 'next_phase_started': False}
save_json(OUT / 'receipt.json', receipt)
evidence = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for folder in [OUT, ARCHIVE]
            for p in folder.rglob('*') if p.is_file() and p.name != 'evidence_sha256.json'}
evidence['CANONICAL.md'] = sha(canonical.read_bytes())
evidence['DECISIONS.md'] = sha(decisions.read_bytes())
save_json(OUT / 'evidence_sha256.json', evidence)
print(json.dumps(receipt, indent=2))
assert run.returncode == 0 and not violations, 'P0 verification failed; see persisted receipt'
