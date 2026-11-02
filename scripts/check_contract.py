"""Check frozen local source hashes without PDF or network dependencies."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'source/FoundingEngineer-Assignment.pdf': 'dc74d7e214479744e998e8471e68104b7790c8845de7241c34c28dd2cfa2db7d',
    # Sponsor's versioned canonical: V3 current; V2 and V1 byte-preserved and independently pinned.
    'CANONICAL.md': '6784499e9e0ac56d26eabac6d34036076890cdbda299da213de32dcd290cc98a',
    'docs/canonical_history/CANONICAL_ORANGE-FOUNDINGAI-20261102-002_FROZEN.md': '32be62a2ec8330328ef57ad5110cbe23a63a84e8f59908aa2355324796115153',
    'docs/canonical_history/CANONICAL_ORANGE-FOUNDINGAI-20261101-001_FROZEN.md': '2f057c7a626174dde3cc35c04a6c4082f2b55e8f49e2b92d2bda43703895b5e2',
    'AGENTS.md': '916ad72dc63ac8dda8c2c89f9966906891096de44ab4e88facecc3f51959d22b',
    'source/ASSIGNMENT_TRANSCRIPTION.txt': 'ebfa24fb394c29dcf1c07096076b3f1e636cb22930d0fc06598bc95b8d254d57',
}


def main():
    result = []
    for relative, expected in EXPECTED.items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        result.append({'file': relative, 'expected_sha256': expected,
                       'actual_sha256': actual, 'match': actual == expected})
    ok = all(item['match'] for item in result)
    print(json.dumps({'gate': 'G0 source contract', 'hash_checks_passed': ok,
                      'files': result}, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
