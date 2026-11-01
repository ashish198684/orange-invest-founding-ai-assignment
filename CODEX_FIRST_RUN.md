# Codex first implementation pass — instructions, subordinate to CANONICAL.md

Read `AGENTS.md`, full `CANONICAL.md` and `source/ASSIGNMENT_TRANSCRIPTION.txt` first. `CANONICAL.md` is the source of truth. Employer PDF (where available) takes precedence. The source PDF is currently in the ZIP provided in ChatGPT; if not present on the local machine, record G0 as incomplete (`ORIGINAL_PDF_NOT_PRESENT`) rather than falsely claiming it was copied. The PDF transcription carries the required tool contract for work to proceed without inventing changes.

Complete **G0 and G1 only** in this pass:
- Inspect existing project and write `docs/implementation_plan.md` mapping each 8 must-haves and all six employer deliverables to exact code/tests.
- Initialize a local git repository only if needed; don't modify/push other repos.
- Implement the employer's **eight** mock provider tools, persistent SQLite slots/holds/bookings/idempotency outcomes and deterministic forced fault scenarios, with `hold_slot` 10-min TTL; `book` 70/15/15 baseline and timeout-after-success persistence; cancel first-503 retry; reschedule conflict; get_booking_status truth.
- Add direct **provider contract tests** proving e.g. timeout-after-success, same-key dedupe and changed-payload rejection, expiry, availability, cancellation/retry, rescheduling/conflict, restarted SQLite state.
- Add `requirements.txt`, README initial 3-command run interface, `docs/actual_progress.md` with reproducible commands/counts and claims boundary. No external API services, no live payments.
- Run tests and preserve exact output/error receipts; end with gate status (`G0 partial if original PDF absent`, `G1 pass only when evidence supports`). Do not start browser/UI, memory or orchestration before G1.

Avoid adding scope not in canonical. Document ambiguities in DECISIONS.md. No need to pause for reapproval on matters already frozen in canonical.