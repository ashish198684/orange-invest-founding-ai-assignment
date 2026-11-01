"""Capture exact local test output, exit status, source hashes, and source snapshot."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def source_files():
    return sorted([*ROOT.glob('app/**/*.py'), *ROOT.glob('tests/**/*.py'),
                   *ROOT.glob('scripts/*.py'), ROOT / 'requirements.txt'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', default='g1_contract')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9_]+', args.label):
        parser.error('label must use lowercase letters, digits and underscores')
    target = ROOT / 'artifacts' / 'receipts'
    target.mkdir(parents=True, exist_ok=True)
    prefix = target / args.label
    if prefix.with_suffix('.json').exists():
        parser.error('receipt already exists; choose a new label')
    files = source_files()
    hashes = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with zipfile.ZipFile(str(prefix) + '_source.zip', 'w', zipfile.ZIP_DEFLATED) as snapshot:
        for p in files:
            snapshot.write(p, p.relative_to(ROOT))
    command = [sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-v']
    started = datetime.now(timezone.utc).isoformat()
    run = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    prefix.with_suffix('.txt').write_bytes(run.stdout)
    output = run.stdout.decode('utf-8', errors='replace')
    count = re.search(r'Ran (\d+) tests?', output)
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    receipt = {'command': command, 'cwd': str(ROOT), 'started_at': started,
               'exit_code': run.returncode, 'tests_run': int(count[1]) if count else None,
               'all_passed': run.returncode == 0, 'source_commit': git.stdout.strip(),
               'working_tree': 'source snapshot and hashes are authoritative for uncommitted changes',
               'source_sha256': hashes}
    prefix.with_suffix('.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(output, end='')
    print('RECEIPT:', prefix.with_suffix('.json'))
    return run.returncode


if __name__ == '__main__':
    raise SystemExit(main())
