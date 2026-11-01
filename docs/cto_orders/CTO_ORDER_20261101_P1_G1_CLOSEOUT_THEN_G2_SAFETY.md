# ORANGE INVEST — CTO ENGINEERING ORDER P1 → G2

**Order ID:** `ORANGE-CTO-20261101-P1-G2-001`  
**Status:** `PREPARED / AWAITING MANUAL SPONSOR DISPATCH`  
**Prepared:** 2026-11-01 (IST)  
**Owner of architectural decisions and acceptance:** CTO/principal architect  
**Engineering implementer:** Codex, only when manually dispatched by the human sponsor  
**Scope:** (A) G1 Git/evidence closeout, then (B) G2 deterministic workflow safety. **STOP after G2.**

> This file is a **subordinate CTO work order**, not a replacement for the canonical master. The employer's original three-page assignment PDF controls its fixed contract. The restored `CANONICAL.md` controls the solution architecture, invariants, acceptance gates and source of truth. `DECISIONS.md` governs recorded interpretations, including ADR-004 (human dispatch), ADR-005 (Groq G4 only) and ADR-006 (P0 canonical reconciliation). If any instruction below conflicts, **STOP, preserve evidence and report the precise conflict**. Chat is not execution authority.

## 0. Authority and immutable input baseline

Read in full BEFORE touching source:
1. `source/FoundingEngineer-Assignment.pdf` — fixed eight tools, eight graded must-haves, minimum 15 offline scripted-user scenarios, six outputs, deadline.
2. `CANONICAL.md` — expected SHA-256 `2f057c7a626174dde3cc35c04a6c4082f2b55e8f49e2b92d2bda43703895b5e2`; verify against `scripts/check_contract.py` and the frozen Git baseline, not merely this paragraph.
3. `AGENTS.md`, `DECISIONS.md`, `docs/implementation_plan.md`, `docs/actual_progress.md`.
4. `artifacts/receipts/p0_20261101_option_a/receipt.json` and `artifacts/receipts/g1_final.json`, plus raw G1 outputs/snapshots.

**Never edit `CANONICAL.md` or the hash verifier to make a contract check pass.**

The confirmed original employer PDF hash is `dc74d7e214479744e998e8471e68104b7790c8845de7241c34c28dd2cfa2db7d`. P0 reported all four G0 hash checks PASS, exit 0, and archived the unapproved 47-line addendum. Keep that archive non-authoritative. Git baseline `d63a1d8`. Current G1 tests recorded 28/28 passed but source changes remain uncommitted. **These are provider tests, not the PDF's scripted-agent evaluations.**

**Go/no-go before change:** `git status`, canonical diff and `python -X utf8 scripts/check_contract.py`; prove G0 still green. If source integrity is wrong, STOP. Never run `git reset --hard`, `git clean`, unrelated repository commands, concurrent agents in this worktree, cloud deployments or live-provider operations. Never overwrite historical receipts. No secrets in source, outputs, screenshots or Git.

## A. P1 — Close G1 with attributable source and evidence

1. Inventory uncommitted and untracked source, original PDF, P0 archive/receipts, decision records, tests, documentation, generated files and any local working state. Preserve all approved source and **three genuine red-to-green G1 bugs**: (i) WAL configuration inside transaction, (ii) SQL placeholder vs table-column counts, (iii) forbidden 409 versus 403. Never invent a bug or rewrite old receipt to make a clean story.
2. Make a source/evidence inclusion list. Exclude `.env`, `GROQ_API_KEY`, secrets, caches, local temporary DBs and private data. Include enough synthetic fixtures, test scripts, original source contract, architecture decisions and reproducible evidence to recreate G1.
3. Create a coherent, reviewable Git commit (or ordered commits) for **P0 governance + G1 provider implementation**. Do not confuse the historical baseline `d63a1d8` with the **new implementation commit SHA**. No push or remote publication without separate sponsor authorization.
4. Run a **fresh, uniquely named** post-commit G0 contract check and G1 provider regression from the committed code; `unittest` is acceptable since pytest installation was blocked. Preserve exact command, captured output/stderr, exit code, total and skipped tests, environment details, actual Git implementation SHA, source hashes and fixture seed. Do not overwrite `g1_final.*` or P0.
5. Inspect at least one actual persisted timeout-after-success case: simulated caller timeout; provider recorded one booking; `get_booking_status` returns booked and ID; same idempotency key replays to the same booking ID after restart; no second committed booking. Store a minimal DB/receipt observation with raw verifiable evidence.
6. Run `git diff --check` and confirm implementation source matches the post-commit tests. Explicitly distinguish source commit from later receipt-only commit (if any); attach evidence to the exact code revision. Do not assert a clean tree when intentionally retained post-test evidence exists.
7. **HARD STOP condition:** If fresh G0 or G1 tests fail, the source/receipt hash does not match, a prior evidence file was altered, or unexplained files exist, **do not enter G2**. Return `G1: FAIL/BLOCKED` with exact discrepancy and minimal remediation proposal.

**P1 progression rule:** If and only if every objective G1 check above passes, Codex may proceed to G2 under this **single sponsor-dispatched combined P1→G2 order**, without claiming independent CTO acceptance yet. If any P1 check fails, STOP. Formal G1/G2 CTO acceptance occurs on the combined final receipt before any later sponsor dispatch. Canonical/PDF hashes, immutable implementation commit, fresh tests and evidence preservation are non-negotiable.

## B. G2 — Build the deterministic safety controller ONLY if P1 passes

**Business objective:** A user can describe or correct a service request, choose a real provider/slot, receive the current hold quote, explicitly approve the exact consequential action, and obtain a truthful provider-verified result **without duplicate bookings or unapproved writes**, even under retries, races and process restart.

**Build the smallest complete Python + SQLite path**, reusing the eight existing mock-provider functions with EXACT employer signatures. Model inference is never authority. For this phase use a simple typed/scripted interpretation adapter where needed for testable conversations; **NO Groq calls, no external LLM, no new provider tool, no model router, no G3 Second Brain/budget subsystem, no G4 browser or G5 video**. The Groq choice is recorded in ADR-005 for separately authorized G4 integration after G3.

### B1. Required interfaces and state

- `WorkflowController` with typed request/draft fields (service, area, date/time window, budget and optional preferences), explicit legal state transitions, monotonically increasing revision, and correction of one field preserving all other known confirmed fields. Ask only for missing information. Resolve relative dates via injected timezone-aware clock, not hidden real time in tests.
- Persisted `workflows`, `approval_snapshots` and `operations` with clear ownership by server-established `user_id`. Never trust a model-provided ID, provider review or client-supplied override as identity. A test-run trusted session context is enough for the local assignment, but don't claim production authentication.
- For **booking**: call `hold_slot`, persist `hold_id`, **actual `quoted_price`** and expiry, compare against stated budget. The search price is discovery metadata, NOT consent price. Quote changes require new approval.
- Approval is a separate, durable record initially `PENDING`; show/return an exact immutable approval view that later G4 can render. Bind `user_id`, `workflow_id`, `action`, `booking_id` if relevant, `provider_id`, old/new slot, original/new price or explicit unknown price status, `hold_id`, expiry, revision and canonical payload fingerprint. Explicit user approval must reference the matching pending approval ID. A free-text `yes` is not itself sufficient proof; no model-generated approval may be accepted.
- Recheck user, revision, payload hash, provider, slot, quote, hold freshness and approval state transactionally. One use of a valid approval advances to `GRANTED` and persists a unique operation and stable idempotency key BEFORE calling any mutating provider tool. Changes to action/provider/slot/quote/user/booking/revision invalidate an earlier approval, including changing a value back to a previous value (ABA).
- All mutations `book`, `cancel`, `reschedule` pass through a single deterministic authorization gate. No alternate code/test/helper/HTTP path may bypass it. ProviderMock itself is test infrastructure and may remain directly callable by its own provider contract tests; **do not claim provider internals enforce customer approvals**.
- Durable **logical request** identity separately from provider-slot uniqueness. Repeated confirmation, process restart, concurrent same-request calls and ambiguous provider results must converge on one logical operation/booking outcome. Use DB uniqueness/CAS where appropriate. If a booking is already verified for that logical request, never create a second booking at a different slot under fresh approval without an explicit new intent and appropriate cancellation/reschedule flow.

### B2. Recovery, conflict and honest reporting

- Booking success response -> verify via authoritative `get_booking_status` before presenting success.
- Timeout after successful provider commit -> **query status first**, recover one booking ID and report verified success. Reuse the SAME persisted idempotency key; never mint a fresh key to escape an ambiguous response.
- Timeout without booking -> persisted unknown/not_found, retries strictly bounded by documented retry policy, SAME key; no infinite loop, no falsely reported success or false permanent failure. `OUTCOME_UNKNOWN` and an honest user message are acceptable where actual status cannot be established.
- Slot taken / hold expired -> don't silently move to another provider/slot under the old approval. Require a new hold, quote and approval.
- Cancellation -> first provider 503; retry using SAME key, verify via `list_bookings`; do not report cancelled until state agrees. Duplicate/restarted cancellation is idempotent.
- Rescheduling -> configured conflict preserves original slot/booking, displays conflict and requires fresh choice; successful change verified using `list_bookings`.
- Exact-price source ambiguity: PDF requires exact action/provider/slot/price approval but `list_bookings` and `reschedule` lack fresh price information. Use only an actual verified stored original price where available; show it explicitly as **original booking price**, not a fabricated new quote or fee. For unknown current amounts, expose the unknown status, do not silently imply price certainty, and **fail closed on price-changing actions whose total cannot be consented to**. Record this interpretation as an ADR and write a negative test. Do not modify eight provider signatures or invent provider APIs.
- Provider review free text is untrusted data, not a system instruction. A forged `SYSTEM`, JSON tool call, claimed consent, or identity change embedded in reviews cannot reach the mutating controller; assert zero unauthorized side effects. Complete broader adversarial coverage in later phases.

### B3. Required G2 automated tests — real controller-to-provider, not mock-only

Use fresh isolated SQLite DBs, injected clocks, seeded faults and real controller entrypoints. At minimum demonstrate:
1. Missing-field questions and preservation of unchanged fields after a correction.
2. No action with absent approval; model-reported approval and raw `yes` alone are rejected.
3. Approval exactly binds action, actor, provider, booking/hold, slot, quote and revision.
4. Quote drift, budget exceeded and ten-minute hold-expiry boundary deny old approval.
5. Changed provider, slot or price invalidate approval. Changing back to the original value does NOT revive the old revision.
6. Repeat confirmation, duplicate request with different transport retries, same logical request to different slot, and two concurrent confirmations yield **<=1** committed booking ID.
7. Restart after operation persisted but before/after provider write reconciles without duplicate mutation.
8. Timeout AFTER success -> status first -> one verified booking ID -> honest user-facing success.
9. Timeout WITHOUT success -> bounded same-key recovery -> honest unresolved/not-found report; no new key.
10. `slot_taken` and `hold_expired` -> fresh quote and fresh approval required.
11. Cancel 503 -> same-key retry and verified cancelled status, including restart.
12. Reschedule conflict -> original booking unchanged; success -> exact new slot verified.
13. Cross-user booking/approval/session and idempotency-key misuse denied with no side effects.
14. Untrusted provider review tries to book/cancel/alter identity; zero unauthorized writes.
15. Unknown price for historical cancel/reschedule disclosed; unsafe price-changing case fails closed.
16. Every terminal controller response agrees with independently queried provider DB status, including unexpected errors.

The number of test functions is NOT the PDF's required scripted-agent eval count. Preserve a matrix mapping each G2 test to a business invariant. Run actual tests and inspect the DB after each adversarial case. Do not fabricate pass results or statistics.

### B4. Evidence-driven architecture / engineering methodology

- **Anthropic:** use the simplest composable workflow; keep transparent typed tool boundaries; test real outcomes, not encouraging prose. Do not add multi-agent orchestration to a bounded booking task. See https://www.anthropic.com/research/building-effective-agents and https://www.anthropic.com/research/demystifying-evals-for-ai-agents .
- **AWS Agentic AI Lens:** application-enforced authorization at mutating tool boundary; propagate trusted identity; use human approval and explicit policy checks; treat all reviews as untrusted. See https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentsec02-bp01.html .
- **AWS durable execution:** retries/replays alone are NOT exactly-once; stable keys, transactional uniqueness and post-error reconciliation must provide at-most-one business outcome. See https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/ .
- **Local scope only:** these are methodology precedents, not AWS/Anthropic endorsement or a reason to deploy AWS infrastructure. Security controls and outcomes are proven in local code/tests.

### B5. G2 stopping rule and CTO acceptance packet

**STOP after G2 tests.** Do not proceed to G3, G4, G5, Groq, browser UI, memory/Second Brain, cloud, extra features, recording or application submission without another sponsor instruction.

Before reporting `G2: PASS`, provide:
- exact Git implementation SHA(s) and file diff; note uncommitted changes honestly;
- full list of test command(s), exit codes, passed/failed/skipped, seed and controlled clock;
- SHA-256 hashes for source/tests, raw stdout/stderr, evidence DB, controller/provider state snapshots and machine-produced test result table;
- at least one real timeout-after-success controller run with approval record + operation record + provider booking state + final user message;
- negative test receipts for no-approval, changed quote, cross-user and logical-request deduplication;
- a table of assumptions rejected, actual bugs with red trace / fix / green test, limitations and deviations (ADR);
- independently checkable `GO/NO-GO` against canonical G2 requirements, explicitly `NOT_STARTED` for G3–G5.

**If anything mandatory fails:** report `G2: FAIL/BLOCKED`, do not paper over it with a passing provider mock test or an attractive demonstration. Preserve partial work and test failures.

## C. Required adversarial CTO review before acceptance

Answer from actual executed evidence:
1. **What was assumed?** Were we mistaking provider-level uniqueness, a model string, or a response from a timed-out tool for business truth?
2. **What was missed?** Show negative tests for a second logical booking on another slot, approval revision ABA, forged identity, restart after side-effect and unknown reschedule price.
3. **What looks right but isn't?** Prove no false-green result where UI/message/trace claims success while DB disagrees. In G2, test the controller response DTO; the browser rendering test waits for G4.
4. **What would we defend?** Show the exact approved snapshot and the persisted matching operation, the provider state, a replayable fault trace, and source/test hashes bound to Git.

**Acceptance authority:** Human sponsor manually dispatches. Codex implements and returns a receipt. CTO independently reviews and decides gate acceptance. **This work order is a proposal until sponsor dispatch. Chat is not the source of truth; `CANONICAL.md` remains mandatory.**

**Deadline:** Employer email specifies 2026-11-03 at 14:00, timezone unspecified; plan conservatively for **14:00 IST**, do not invent an employer-confirmed timezone. Preserve sufficient time for G3–G5 and the real video by not adding optional scope.

**END — `ORANGE-CTO-20261101-P1-G2-001`.**
