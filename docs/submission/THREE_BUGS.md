# Three Real Defects — Failure, Cause, Fix, Regression

These are **observed failures**, not hypothetical examples. Red receipts are retained; successful replays are tied to the released source. Local fixture users and hashes are synthetic.

## Bug 1 — Real browser clicks silently dropped

**Symptom.** Early Chromium replay failed to advance after an interaction: `artifacts/receipts/g4_browser_first_20261103/receipt.json`, including the failure screenshot and browser events. UI actions arriving while a request was active were ignored.

**Root cause.** `app/web/app.js` implemented `work(fn)` using `if(state.busy)return`: a user click during a pending fetch was discarded rather than serialized. The UI could appear responsive while failing to honor an explicit intent.

**Correction.** Serialize UI jobs through a promise queue; maintain consistent pending/button state and handle errors. Do not repeat operations by blindly retrying provider mutations.

**Regression evidence.** `artifacts/receipts/g4_browser_queuefix_20261103/receipt.json` passed a real Chromium journey. Final `g4_release_20261103e/browser/receipt.json` covers immutable approval, correction, recovery and user controls.

## Bug 2 — Provider already committed, but worker declared unresolved too early

**Symptom.** `artifacts/receipts/g4_fresh_rpcfix_20261103/regressions/pg_tests.txt` records failure in `test_provider_process_dies_after_commit_restarted_workers_reconcile`. The provider had committed a booking before a crash, but repeated rapid status checks could exhaust the recovery claim budget before the service restarted.

**Root cause.** Six near-immediate one-second status retries were consumed faster than the provider restart. Idempotency by itself was insufficient: reconciling too aggressively can still terminate a durable workflow prematurely.

**Correction.** `app/runtime/worker.py` uses persisted bounded backoff, retaining the original operation key, write-attempt limit and five-minute recovery horizon. No new booking key is invented.

**Regression evidence.** `artifacts/receipts/g4_fresh_recoveryfix_20261103/regressions/pg_tests.txt` passed all 39 distributed tests; final `g4_release_20261103e/regressions/pg_tests.txt` independently passed. The E12 evaluator and full raw trace prove timeout→readback→single booked outcome.

## Bug 3 — Logout attempted a forbidden database mutation

**Symptom.** `artifacts/receipts/g4_release_20261103d_browser/receipt.json` failed after the browser had already successfully booked, rescheduled and cancelled. The raw sanitized `handler_error` identified `InsufficientPrivilege`; `artifacts/receipts/g4_logout_diagnostic_20261103.json` preserves the corrected root-cause determination.

**Root cause.** Logout executed `DELETE FROM sessions`, but the tightly scoped application role deliberately had only SELECT/INSERT/UPDATE permissions. An initial foreign-key hypothesis was *not* the confirmed cause.

**Correction.** Replace DELETE with `UPDATE sessions SET expires_at=clock_timestamp()`; session access is revoked without broadening database privilege or destroying approval audit references.

**Regression evidence.** `artifacts/receipts/g4_logout_verified_20261103.json` independently verifies the expired session via SQL; final real Chromium `g4_release_20261103e/browser/receipt.json` passed logout and the full journey.

## Additional model failure transparently retained

### Later live review defect Send flicker during polling

The older UI sent idle status polling through the same foreground pending-state helper as user actions. Eight unwanted disabled-state changes were reproduced in the [RED receipt](../../artifacts/receipts/g5_polling_red_20261103/receipt.json). Release `ac1493e` separates foreground pending state from background status-only refresh. The [release browser regression](../../artifacts/receipts/g5_release_live_browser_20261103/receipt.json) observed zero changes over 14.5 seconds, then completed an explicitly approved timeout-after-success booking. The separate alice `slot_taken` outcome was reconciled to zero bookings; improved copy explains that recorded conflict truthfully.

### Model failures and grounding

Strict Groq schema mode intermittently returned HTTP 400 `json_validate_failed` after omitting nullable fields; the v3 prompt explicitly specifies all fields and still validates independently. A real live model also paraphrased “morning,” causing the validator to discard its proposed limit. The code grounded it against explicit source phrases. See `artifacts/receipts/g4_groq_schema_diagnostic_20261103.json`, `g4_browser_live_candidate_20261103_screens`, 20 final adapter tests and the final live/model audit. This is **not** a claim of broad reliability or immunity to prompt injection.
