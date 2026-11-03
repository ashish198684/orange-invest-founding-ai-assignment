Current engineering evidence: [G3X handoff](g3x_handoff.md). G3X technical checks passed; CTO acceptance pending. G4/G5/Groq remain unstarted and submission remains NO-GO. The records below are historical.

﻿# Actual progress - G0/G1 only

Observed on 2026-11-01 in `C:/Users/marke/Desktop/OrangeInvest-FoundingAI-Assignment`.
Python 3.12.10; SQLite 3.49.1. Existing local Git repository retained; baseline
`d63a1d8c313797135a6c1c1c8703c7d7723df780`. Changes are **NOT_COMMITTED**; no push or
remote repository changes. Full code/test source snapshots accompany test receipts.

## Gate receipts

```text
GATE: G0 | status: PASS
COMMIT: NOT_COMMITTED (baseline d63a1d8c313797135a6c1c1c8703c7d7723df780)
COMMAND: python scripts/check_contract.py
EXIT_CODE: 0
TESTS: 0/0 (source verification, not application tests); HASH_CHECKS: 4/4; SKIPPED: 0
EVIDENCE: C:/Users/marke/Desktop/OrangeInvest-FoundingAI-Assignment/artifacts/receipts/g0_contract.txt
SHA256: 772a0586a9f84c02badbcec79e7d6f6883dab064df33996c29d242ac028dd7a4
OBSERVATION: Original three-page PDF found locally, copied unchanged; frozen PDF,
canonical, AGENTS and transcription hashes match. Plan and architecture ADRs exist.
REJECTED_ASSUMPTIONS: PDF was absent from the initial repository, but a matching
original was available in Downloads. G0 is not ORIGINAL_PDF_NOT_PRESENT.
NEXT: G1 provider persistence and contract proof (completed below).

GATE: G1 | status: PASS
COMMIT: NOT_COMMITTED (baseline d63a1d8c313797135a6c1c1c8703c7d7723df780)
COMMAND: python -X utf8 scripts/run_checks.py --label g1_final
CHILD_COMMAND: python -X utf8 -m unittest discover -s tests -v
EXIT_CODE: 0
TESTS: 28/28; SKIPPED: 0
EVIDENCE: C:/Users/marke/Desktop/OrangeInvest-FoundingAI-Assignment/artifacts/receipts/g1_final.txt
SHA256: e71955e05f84a4b5ae56bdbed10bea24bbffee6fea31f4a98af6f0b9b3704d55
EVIDENCE: C:/Users/marke/Desktop/OrangeInvest-FoundingAI-Assignment/artifacts/receipts/g1_final.json
SHA256: 4c4c06b1ceb3afc2c887141811fe1768de2afe9547008c007efd7968352de7b4
OBSERVATION: All eight signatures, required response shapes and deterministic
fault branches exercised; real subprocess exit after provider timeout preserves
one booked ID and outcome. Cancellation's first 503 survives restart; same-key
retry cancels. Configured/occupied/held reschedule conflicts retain old slot.
REJECTED_ASSUMPTIONS: SQLite WAL mode cannot be changed inside BEGIN; placeholders
must match the eight-column tables; forbidden writes need HTTP 403. Pytest was
not available and installation stalled; unittest executed the actual suite.
NEXT: G2 safety/controller work in a later pass; not started here.
```

The `g1_final` label is immutable. Reproduce with
`python -X utf8 scripts/run_checks.py --label g1_recheck_1`, choosing a new label;
or run the direct child command. The recorded 28 tests include parameterized
unittest subtests. **They are direct provider tests, not the employer's E01-E28
scripted-user agent evaluations.** No end-to-end eval count is claimed.

`artifacts/receipts/sha256_manifest.json` contains absolute paths and hashes for
source, documentation, copied PDF, receipts and source snapshots (excluding the
manifest itself). `gate_status.json` contains structured gate receipts. The
canonical, original PDF and transcription were not edited.

## Observed implementation and evidence

- `app/provider_mock/tools.py`: exactly eight public tool methods. Trusted user
  context stays outside fixed signatures. Reviews contain actual malicious free
  text; only its presence/no provider side effects is proven at this gate.
- `app/storage.py`: persistent provider slots/holds/bookings/outcomes/config,
  foreign keys, WAL, busy timeout, short writer transactions and partial unique
  active provider/slot index. Startup preserves data; explicit `reset-demo` is a
  separate tested command. No workflow/approval/memory tables are implemented.
- `fixtures.py` / `scenario_engine.py`: persisted synthetic fixture configuration,
  configurable quote increase, exclusive 600-second holds, stable seeded baseline
  and individually forced fault branches. Supported searches yield three varied
  providers. Unknown fixture service/area yields no matches (ADR-002).
- Direct tests prove same-key response dedupe after hold expiry/restart, changed
  payload/cross-action rejection, provider-user isolation, expired holds/reholds,
  separate-connection races, actual fresh-process persistence, cancellation retry,
  reschedule success/conflicts and explicit reset distinct from startup.
- Statistical smoke (10,000 stable seeds, not full booking trials): success 7,041
  (70.41%); slot_taken 1,517 (15.17%); timeout-after-success 723 and timeout-without-
  booking 719 (combined 14.42%). This is an approximate distribution check; forced
  branch tests separately assert actual provider effects.

`python -X utf8 scripts/provider_probe.py` exited 0 and created a preserved direct
provider evidence DB (the command refuses to overwrite it). Its receipt is
`artifacts/receipts/provider_timeout.json` (SHA-256
`83f90c119755e32ad22f04ff4c4da37814cf13bea3fe64938e1a198753ab3309`).
The caller observed timeout/504, reopened SQLite, read booked ID
`703615d78d944250abc896121c2a8735`, replayed the same key to the same ID and found
one booking. Hold status is consumed; outcome error is timeout_after_success;
SQLite integrity_check is ok. The database itself is
`artifacts/receipts/provider_timeout.sqlite3` (SHA-256
`ddbac5863b495a015ae69a85fed4ffd3e33358e507c643dda021bbc866f9643e`).
This probe is not an approval-controlled workflow or the required end-to-end trace.

`python -X utf8 -m app.provider_mock` exited 0 and printed three providers; receipt
`artifacts/receipts/provider_inspection.json`. Inspection DB contained 18 providers,
378 slots, zero holds, zero bookings, zero operation outcomes. The DB under
`data/` is ignored local demo state, not committed evidence.

## Actual failures retained

| Observed defect | Red evidence | Fix and green regression |
| --- | --- | --- |
| WAL set after transaction began | `g1_first_run.txt`: Ran 23 tests; FAILED (errors=42); app/test source in `g1_first_run_source.zip` | Configure WAL in autocommit connection before transactional operations; `test_sqlite_constraints_and_restart_config` and fresh DB tests pass in final receipt |
| Nine SQL placeholders for eight-column bookings/outcomes | `g1_after_wal_fix.txt` and `g1_after_insert_fix.txt`: Ran 23 tests; FAILED (failures=1, errors=28); JSON and source snapshots retained | Use eight placeholders for both tables; forced branch, restart and direct status tests pass in final receipt |
| Forbidden write carried generic 409 instead of 403 | `g1_after_outcome_fix.txt`: Ran 23 tests; FAILED (failures=1) | Map forbidden to 403; `test_user_isolation_hold_booking_status_and_key` passes in final receipt |

These are observed implementation failures, with preserved source and raw output;
they are not invented production incidents. No separate final bug deliverable or
commit for these uncommitted changes is claimed.

Other environment errors: `pytest_preflight.txt` captures actual missing-module
output (exit 1). `dependency_diagnostic.json` captures an isolated pip dry-run
terminated after 25 seconds with no package output; its exit code is null because
it timed out. Initial PDF extraction hit cp1252's rupee-character encoding error;
UTF-8 extraction succeeded and all three pages are in `pdf_extraction.txt`.
README provides a dependency-free three-command interface; optional pytest is
pinned but its successful installation/execution is not claimed (ADR-003).

## Claims boundary and remaining gates

G2, G3, G4 and G5: **NOT_STARTED**. No parser, workflow, stored approvals, logical
request dedupe, run budgets, memory, trace system, browser/UI, scripted-user eval
CSV/JSON, design note, screen recording or full submission is implemented or
accepted. Provider-level correctness cannot prove those later invariants. No
model-proposed actions exist; the future controller must check persisted approval
and reconcile status before reporting any write outcome. No screenshots or demo
link exist in this pass. The plan maps all remaining must-haves and deliverables.


## 2026-11-02 sponsor-dispatched P1 -> G2 update

The earlier sections are historical G1 observations, not current completion claims.
G1 source/governance commit: 32e707cdb0c4fb509455e0d2525f196e756d49ac;
fresh receipt-only commit: 4685c4abc1481a58daec61ea40e467b0f6408788.
Post-commit G0 4/4 and G1 28/28 passed, skipped 0, commands exit 0, source bytes
match Git and historical receipts are unchanged. Receipt:
artifacts/receipts/p1_postcommit_20261101/receipt.json.

G2 now has a real persisted controller and scripted proposal adapter. The expanded
candidate passed 65/65 tests (28 provider + 37 controller), zero skipped, and 38/38
independent SQL evidence-DB inspections. Final committed-source G2 counts and SHA
are established only by artifacts/receipts/g2_postcommit_20261102/receipt.json
once generated; see docs/g2_handoff.md and ADR-007 for scope, bugs and limitations.
The canonical remains pinned to 2f057c7a626174dde3cc35c04a6c4082f2b55e8f49e2b92d2bda43703895b5e2.
G3-G5/Groq NOT_STARTED. Employer submission remains NO-GO; stop after G2 for CTO review.
