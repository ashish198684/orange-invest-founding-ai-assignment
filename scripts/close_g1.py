"""Fresh post-commit P1 evidence. Refuses overwrites; checks committed source bytes."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import platform
import re
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.provider_mock import ProviderMock, ProviderTimeout, ScenarioConfig

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out = ROOT / 'artifacts/receipts/p1_postcommit_20261101'
    out.mkdir(exist_ok=False)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    pre = json.loads((ROOT / 'artifacts/receipts/p1_preflight_20261101.json').read_text())
    changed = [p for p,h in pre['historical_evidence_sha256'].items() if digest(ROOT / p) != h]
    assert not changed, changed
    sources = sorted([*ROOT.glob('app/**/*.py'), *ROOT.glob('tests/**/*.py'), *ROOT.glob('scripts/*.py'),
                      ROOT/'CANONICAL.md', ROOT/'AGENTS.md', ROOT/'requirements.txt'])
    hashes = {}
    for p in sources:
        rel = p.relative_to(ROOT).as_posix()
        committed = subprocess.check_output(['git', 'show', f'{head}:{rel}'], cwd=ROOT)
        assert committed == p.read_bytes(), f'Uncommitted source: {rel}'
        hashes[rel] = digest(p)
    commands = []
    for label, args in [('g0', ['scripts/check_contract.py']),
                        ('g1', ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_provider_contract.py', '-v'])]:
        command = [sys.executable, '-X', 'utf8', *args]
        run = subprocess.run(command, cwd=ROOT, capture_output=True)
        (out/f'{label}_stdout.txt').write_bytes(run.stdout)
        (out/f'{label}_stderr.txt').write_bytes(run.stderr)
        commands.append({'command': command, 'exit_code': run.returncode})
        assert run.returncode == 0, f'{label} failed: {run.stderr.decode()}'
    text = (out/'g1_stderr.txt').read_text()
    count = int(re.search(r'Ran (\d+) tests', text)[1])
    assert count >= 28 and 'skipped' not in text.lower()
    clock = lambda: datetime.fromisoformat('2026-11-01T09:00:00+05:30')
    path = out/'provider_timeout.sqlite3'
    p = ProviderMock(path, user_id='p1-synthetic', clock=clock,
                     config=ScenarioConfig(book_branch='timeout_after_success'))
    option = p.search_providers('plumber', 'Indiranagar', {
        'start': clock().isoformat(), 'end': '2026-11-09T09:00:00+05:30'})[0]
    hold = p.hold_slot(option['id'], option['free_slots'][0])
    try:
        p.book(hold['hold_id'], 'p1-stable-key')
        raise AssertionError('Expected timeout')
    except ProviderTimeout:
        pass
    p = ProviderMock(path, user_id='p1-synthetic', clock=clock)
    status = p.get_booking_status('p1-stable-key')
    replay = p.book(hold['hold_id'], 'p1-stable-key')
    assert status['status'] == 'booked' and replay['booking_id'] == status['booking_id']
    assert len(p.list_bookings('p1-synthetic')) == 1
    with p.store.connect() as db:
        observation = {table: [dict(r) for r in db.execute(f'SELECT * FROM {table}')]
                       for table in ['provider_holds','provider_bookings','provider_operation_outcomes']}
        observation['integrity_check'] = db.execute('PRAGMA integrity_check').fetchone()[0]
    observation.update(caller_observed='timeout', authoritative_status=status, same_key_restart_replay=replay)
    (out/'provider_observation.json').write_text(json.dumps(observation,indent=2)+'\n',encoding='utf-8')
    for rel,h in hashes.items():
        assert digest(ROOT/rel) == h
    assert all(digest(ROOT/p)==h for p,h in pre['historical_evidence_sha256'].items())
    diff = subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True)
    assert diff.returncode == 0, diff.stdout
    receipt = dict(phase='P1 G1 objective checks', status='PASS; CTO acceptance pending', source_commit=head,
                   commands=commands, tests_passed=count, tests_run=count, skipped=0,
                   python=sys.version, sqlite=sqlite3.sqlite_version, platform=platform.platform(),
                   clock=clock().isoformat(), seed=20261101, source_sha256=hashes,
                   historical_evidence_unchanged=True, source_matches_commit=True, diff_check_exit_code=0)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    manifest = {p.relative_to(ROOT).as_posix():digest(p) for p in out.iterdir() if p.is_file()}
    (out/'sha256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__ == '__main__':
    main()
