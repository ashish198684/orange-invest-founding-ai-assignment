# G2 engineering handoff - 2 November 2026 IST

Order ORANGE-CTO-20261101-P1-G2-001, manually dispatched by sponsor. The frozen
canonical and employer contract are unchanged. Stop at G2; CTO adjudication is
pending. The complete employer submission remains NO-GO.

## Attributable G1 closeout

- Implementation + P0 governance: `32e707cdb0c4fb509455e0d2525f196e756d49ac`.
- Receipt-only commit: `4685c4abc1481a58daec61ea40e467b0f6408788`.
- `scripts/close_g1.py`: G0 4/4, provider tests 28/28, skipped 0, all exit 0;
  every source byte matches its committed Git blob. Fresh persisted timeout,
  authoritative booked status and same-key/restarted replay produced one ID.
- Receipt: `artifacts/receipts/p1_postcommit_20261101/receipt.json`; exact commands,
  Python/SQLite/platform, seed, clock, raw outputs and hashes are included.
- Historical G0/G1/P0 evidence is unchanged, including all three authentic G1
  failure categories and their original ZIPs. No push/publication occurred.

## Implemented G2 behavior

`app/workflow.py` owns draft revisions, immutable approval snapshots, operation
records, stable keys, logical-request uniqueness and mutation/recovery. It reuses
all eight unchanged provider signatures. `app/agent/scripted.py` only proposes
validated constraints. Review text is wrapped as untrusted data and never sent
through a customer-input action path. No model has mutation/approval authority.

The trusted embedding server/test context supplies user identity. `chat` and
`propose` cannot grant approval. Customer confirmation must separately identify
the current pending approval. Every mutation executes from a persisted granted
snapshot; all relevant revision/payload/hold/price/identity checks are repeated.
An operation key is generated once by the controller; transport clients cannot
replace it. One logical request cannot become a second booking on another slot,
including after an unresolved timeout. A distinct new intent is explicit via a
new logical request ID, not an automatic recovery mechanism.

SQLite write transactions are short. A kernel file lock serializes local
provider execution/read-back across connections/processes and is released by
process death. The operation remains in SQLite across that death. Recovery reads
authoritative status before any replay. Each operation has a durable maximum of
three mutation attempts (first attempt + two retries); repeated restarts do not
reset it. Timeout-without-booking ends OUTCOME_UNKNOWN, never fabricated success
or a fresh key. The lock is local, not a distributed workflow or general G3 run
budget. A later server must call `recover()` on startup before dispatching writes.

Successful book checks status, provider ID, booking ID and exact approved slot.
Cancel checks list_bookings after the same-key 503 retry. Reschedule conflicts
retain the original slot; success reads back the exact new slot. Original booking
price is labelled as original; unknown prices are disclosed. The fixed mock
charges no new fees. Requests involving a price-changing action are blocked
because the contract provides no authoritative fresh total (ADR-007).

## Executed evidence and acceptance boundaries

The first expanded candidate passed 65/65 tests: 28 G1 provider tests plus 37 G2
controller tests, zero skipped. Separate read-only SQL inspection checked 38
preserved evidence DBs: integrity/FKs, provider-slot uniqueness, logical-request
uniqueness, matching granted approval/payload for controller-created bookings,
and durable retry limits. No violations were found. These are actual G2 tests,
not the employer's G4 scripted-agent evaluation count.

The final committed-source receipt is generated separately with:

```
python -X utf8 scripts/g2_evidence.py --label g2_postcommit_20261102 --require-committed
```

That receipt is authoritative for final counts/commands/exit codes/source commit
and source/test/evidence hashes. Its `cases/` contains actual per-test SQLite
backups, JSON state and call logs. Its `timeout_probe/` contains the exact approval,
granted operation, provider timeout, read-back, final customer message, restart
and duplicate confirmation, plus one provider booking. This probe is evidence
instrumentation, not a claimed implementation of G3's application trace system.
The final receipt and manifest name the exact G2 implementation SHA; subsequent
receipt-only commits do not change that source attribution.

## Actual G2 failures, fixes and regressions

| Defect | Real red receipt and source snapshot | Fix and executed regression |
|---|---|---|
| Operation INSERT had 15 values for 14 columns | `g2_first_implementation_20261102.txt` + `_source.zip` | Explicit 10 immutable/core column names, remaining columns use defaults; exact-approval, normal book and all lifecycle tests pass |
| VERIFYING had no legal edge back to EXECUTING for a checked same-key retry | `g2_after_sql_connection_fix_20261102.txt` + `_source.zip`: four errors | Add only the explicit retry transition; cancel 503, unknown timeout and historical cancellation tests pass |
| Booked ID/provider check missed a changed provider-side slot | `g2_adversarial_readback_red_20261102.txt` + `_source.zip`: 1/65 failed | Compare exact approved slot during authoritative read-back; `test_provider_booked_different_slot_is_not_approved_success` now passes with OUTCOME_UNKNOWN and one actual booking |

Initial `g2_red_initial_20261102` is an expected missing-controller test-first red,
not an application defect. A Windows test-fixture connection leak was also fixed:
SQLite's connection context commits/rolls back but does not close the handle;
`contextlib.closing` now closes inspection connections. All original logs/snapshots
remain untouched. The final commit diff is inspectable against G1 receipt commit.

## Adversarial assessment

| Challenge | Evidence-based answer |
|---|---|
| What was assumed? | Provider uniqueness was insufficient. Logical workflow identity and persisted operation/approval checks now independently constrain business intent. A model string/raw yes cannot authorize. |
| What was missed? | Negative tests cover a second slot under the same logical request, revision ABA, forged user/approval/operation identity, crash after provider success, and unknown reschedule price. The expanded wrong-slot test found a real false-green response and drove a fix. |
| What looks right but isn't? | A successful tool response can coexist with zero bookings, an inaccessible status API, or a different actual slot. Each produces an unresolved response. A historical BOOKED receipt is not current truth after cancellation; repeating an old operation reads provider state again. |
| What would we defend? | The immutable approved snapshot matches the durable operation and actual provider record; timeout/restart evidence shows one key/booking. SQL inspection and per-case artifacts are independent of reassuring response prose. |

## Limits and stop

No production authentication or HTTP/browser path is claimed. The minimal parser
supports only documented fixture vocabulary/date expressions; general language
quality waits for G4. Unused/over-budget/stale holds expire at provider TTL because
the fixed contract has no release-hold tool. Unknown outcomes remain locked until
authoritative reconciliation; they cannot be escaped by re-keying. SQLite/OS-lock
coordination assumes the same local DB and filesystem. A hung tool and complete
model/tool/wall-time budgets are deferred G3 work, not proven here. Price-changing
reschedules are intentionally unavailable under the fixed provider contract.

G3 memory/limits/full trace, G4 browser/Groq/evaluations and G5 deliverables/video
remain NOT_STARTED. No optional feature, cloud infrastructure or live provider
was implemented. Formal GO/NO-GO belongs to the CTO after this receipt review.

Methodology references actually consulted (not endorsements):
[Anthropic workflows](https://www.anthropic.com/research/building-effective-agents),
[AWS tool authorization](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentsec02-bp01.html),
[AWS idempotency](https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/).
