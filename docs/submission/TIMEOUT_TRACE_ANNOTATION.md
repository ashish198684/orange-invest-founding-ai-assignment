# Timeout-after-success: annotated, unmodified worker trace

**Source of truth:** [raw JSONL](../../artifacts/traces/timeout_after_success.jsonl). No entries have been edited or regenerated for this explanation.

**Exact tested source:** `b6d4bb72e5108e691fe38d1dfc994cf7dae8771c`. **Trace run:** `8a0de1ad493e499386d733192c360f43`, workflow `e37ef16999cd4d1fb898098967f6789f`; hashed operation `3bf4f6ae3c38b0d2941c9b12b7856b5ca516418c7b423ff83c15cc86b5de3291`. The idempotency key itself is not disclosed; its stable hash appears on the tool events.

| Sequence | Actual raw event | Why it matters |
|---|---|---|
| 1 | `job_claim` | Durable worker claims generation 1 of the logical operation |
| 2–3 | `get_booking_status` → `not_found` | Status-first check before performing the write |
| 4–5 | `workflow_transition` → `EXECUTING`; `book` request | Provider write occurs only after a separately confirmed approval |
| 6 | `provider_timeout`, `ProviderTimeout`, `OUTCOME_UNKNOWN` | Network reply is inconclusive—**not** proof booking failed |
| 7 | `workflow_transition` from `EXECUTING` to `VERIFYING` | Prevents a false failure claim or immediate duplicate booking |
| 8–9 | `get_booking_status` → `booked` | Same logical key reconciles a provider-side commit after the lost response |
| 10–11 | `list_bookings` → count 1 | Additional independent provider readback |
| 12 | `workflow_transition` `VERIFYING` → `BOOKED` | UI can now truthfully report success based on authoritative evidence |

The raw trace has 13 JSONL records. Final scenario E12 also retains the related API requests, exact approval snapshot and provider SQL:
`artifacts/receipts/g4_release_20261103e/evals/E12/`. The independent live/browser audit in `g4_release_20261103e/audit/receipt.json` confirms one logical effect per booked operation; it must not be confused with a separate real-Groq run.

**Contract invariant:** The system may retry reads under a bounded budget; it must never mint a new booking key or claim the booking failed merely because the response timed out. If the provider cannot establish the outcome within the recovery horizon, report `OUTCOME_UNKNOWN` and preserve the operation for operator reconciliation.
