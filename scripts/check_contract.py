"""Check frozen local source hashes without PDF or network dependencies."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'docs/canonical_history/CANONICAL_EXECUTION_5b87066b7ef18b2c6d6f3d84e43580d8c0ddcb18cb6d43bced65be9b87a5f625_FROZEN.md': '5b87066b7ef18b2c6d6f3d84e43580d8c0ddcb18cb6d43bced65be9b87a5f625',
    'docs/canonical_history/CANONICAL_EXECUTION_fb26e05511fc57551bbb19ff5becf3ef2fff10a25df65bfc57d62cad3ab486a0_FROZEN.md': 'fb26e05511fc57551bbb19ff5becf3ef2fff10a25df65bfc57d62cad3ab486a0',
    'docs/canonical_history/CANONICAL_EXECUTION_2a93021fd8e3aed0d6c9cef3323716aec0308db3bc5b1cdaf37866a7ce9c7fb9_FROZEN.md': '2a93021fd8e3aed0d6c9cef3323716aec0308db3bc5b1cdaf37866a7ce9c7fb9',
    'docs/canonical_history/CANONICAL_EXECUTION_29afaa8839cfdcbb6965099e9135230b0a685232ea06141445acb3e96953c5dc_FROZEN.md': '29afaa8839cfdcbb6965099e9135230b0a685232ea06141445acb3e96953c5dc',
    'docs/canonical_history/CANONICAL_EXECUTION_cea69f53463d936b7e8cebd8b90d66371ae1a268370527d88a5be2886922f0b2_FROZEN.md': 'cea69f53463d936b7e8cebd8b90d66371ae1a268370527d88a5be2886922f0b2',
    'docs/canonical_history/CANONICAL_EXECUTION_fb47ac89af5d4a04cf200f855f27dfb574f57c577b05004d608cb910cf3bcecd_FROZEN.md': 'fb47ac89af5d4a04cf200f855f27dfb574f57c577b05004d608cb910cf3bcecd',
    'docs/canonical_history/CANONICAL_EXECUTION_1e02c7e22b257dd165259e0e03ae4972e3cc974c9b7ac7853b5f93c8876941b4_FROZEN.md': '1e02c7e22b257dd165259e0e03ae4972e3cc974c9b7ac7853b5f93c8876941b4',
    'docs/canonical_history/CANONICAL_EXECUTION_43f4058cea8da3ccddb2bcd0ac6bfb11af26c27163f3c690c543a23831fdda54_FROZEN.md': '43f4058cea8da3ccddb2bcd0ac6bfb11af26c27163f3c690c543a23831fdda54',
    'docs/canonical_history/CANONICAL_EXECUTION_1765e03a3fad899fed1f4abe0fb3d966fa23fc283b5cd372c3883e26c474d84f_FROZEN.md': '1765e03a3fad899fed1f4abe0fb3d966fa23fc283b5cd372c3883e26c474d84f',
    'docs/canonical_history/CANONICAL_EXECUTION_33f46a8db52f1ae0745ab885e1c511d85d2615e21d558ba8749656deb67a70d8_FROZEN.md': '33f46a8db52f1ae0745ab885e1c511d85d2615e21d558ba8749656deb67a70d8',
    'docs/canonical_history/CANONICAL_EXECUTION_c5c49bb79a9913012283fd79682f392fea27741f0428f5fc8edc3aa0643d325e_FROZEN.md': 'c5c49bb79a9913012283fd79682f392fea27741f0428f5fc8edc3aa0643d325e',
    'docs/canonical_history/CANONICAL_EXECUTION_197a32bb0dcaf51eee3c25845feb3de5214f1fb8a7e9e5b57e90ca0c35546669_FROZEN.md': '197a32bb0dcaf51eee3c25845feb3de5214f1fb8a7e9e5b57e90ca0c35546669',
    'docs/canonical_history/CANONICAL_EXECUTION_a819447f374770550e4228779a5f7b1b8e37f5e4f33f5bc0a2ddf3d7c0bb2684_FROZEN.md': 'a819447f374770550e4228779a5f7b1b8e37f5e4f33f5bc0a2ddf3d7c0bb2684',
    'docs/canonical_history/CANONICAL_EXECUTION_cf6d10eed84b12c4776b6ea54b7cb3d0fe44b64ff52c8a8ecfd986b0ca158265_FROZEN.md': 'cf6d10eed84b12c4776b6ea54b7cb3d0fe44b64ff52c8a8ecfd986b0ca158265',
    'docs/canonical_history/CANONICAL_EXECUTION_4a5dcdb85c58922e335c25f7cff449203a5d04faad98945f2bfbfc58f702b977_FROZEN.md': '4a5dcdb85c58922e335c25f7cff449203a5d04faad98945f2bfbfc58f702b977',
    'docs/canonical_history/CANONICAL_EXECUTION_6784499e9e0ac56d26eabac6d34036076890cdbda299da213de32dcd290cc98a_FROZEN.md': '6784499e9e0ac56d26eabac6d34036076890cdbda299da213de32dcd290cc98a',
    'source/FoundingEngineer-Assignment.pdf': 'dc74d7e214479744e998e8471e68104b7790c8845de7241c34c28dd2cfa2db7d',
    # Sponsor's versioned canonical: V3 current; V2 and V1 byte-preserved and independently pinned.
    'CANONICAL.md': 'd1cd7cbb7687d943d5fd225fa83ca8d74081e35de96a330893dedb9b29a726de',
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
