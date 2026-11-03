# Implementation plan - G0/G1 pass, 2026-11-01

## G4 dispatch / 2026-11-03

The sponsor dispatched Section P4. Historical plans below remain unchanged.
G4 adds `app/web/` over the accepted authenticated HTTP/controller boundary;
`scripts/g4_browser.py` executes actual Chromium interactions and screenshots;
`scripts/g4_evals.py` drives 28 scripted-user HTTP journeys and independent
read-only provider/authority SQL graders, retaining all failures and raw traces.
Its private HTTP test server uses the production Handler with a fixed injected
interpreter clock and delayed queue availability so real worker subprocesses can
be killed/restarted reproducibly. Those constructor overrides are not API fields.
Existing 65 SQLite and 39 G3X regressions remain separate checks. Next, a versioned
Groq proposal adapter will be enabled separately with server-only environment
injection; offline defaults and all consent/operation authority remain unchanged.
The final G4 receipt binds screenshots, SQL, traces, source hashes and exact exits.
Stop at G4; G5/video/submission/push remain outside this dispatch.

Authority: full `CANONICAL.md` (ORANGE-FOUNDINGAI-20261101-001), `AGENTS.md`,
`source/ASSIGNMENT_TRANSCRIPTION.txt`, and original three-page PDF. The PDF was
found in Downloads; SHA-256 matches the frozen contract and it is copied unchanged
to `source/FoundingEngineer-Assignment.pdf`. Existing repository root matches this
workspace; retain its history. No other repository or cloud resources are used.

## Gate order and claims

This pass implements G0 and G1 only. G2 safety, G3 memory/trace/budgets, G4 UI/evals,
and G5 submission evidence remain planned. Direct provider calls are test-facing
infrastructure, not a user-facing agent or an approval bypass exposed to chat.

| Must-have | Exact planned ownership | Proof / gate |
| --- | --- | --- |
| 1 Explicit workflow; retain corrections | `app/domain.py`, `app/workflow.py`, `app/agent/interpreter.py` | `tests/test_workflow.py`: missing fields, correction retention (E01/E02), G2 |
| 2 Code approval; invalidate changes | `app/approvals.py`, `app/storage.py` | `tests/test_approval.py`: missing/forged/expired approval, provider/slot/price/revision changes (E06-E10), G2 |
| 3 Booking correctness/recovery | G1: `app/provider_mock/tools.py`, `app/provider_mock/scenario_engine.py`, `app/storage.py`; G2: `app/operations.py` | G1 `tests/test_provider_contract.py`: faults, stable keys, restart, races; G2 `tests/test_recovery.py` E11-E22, logical intent/repeated yes/approval concurrency |
| 4 Untrusted free text | G1 malicious fixture in `app/provider_mock/fixtures.py`; G2 `app/agent/interpreter.py` | G1 review presence; G2 `tests/test_security.py` E04/E05: no permission, identity or memory changes |
| 5 Bounded execution | `app/budgets.py`, `app/workflow.py` | `tests/test_budgets.py` E26/E27: tool/model/monotonic caps and honest terminal replies, G3 |
| 6 User memory rights | `app/memory.py`, `app/storage.py` | `tests/test_memory.py` E23-E25: view/correct/forget, provenance, inferred confirmation, user isolation, G3 |
| 7 Per-run traces | `app/trace.py`, later `app/web/app.js` | `tests/test_trace.py`: redaction, ordering, null unavailable cost/tokens, terminal evidence, G3 |
| 8 Offline scenario evals | `tests/evals/scenarios.py`, `scripted_users.py`, `grade.py` | E01-E28, DB+trace+reply grading; generated CSV/JSON, G4; provider unit tests are not these evals |

| Employer deliverable | Exact file / evidence | Acceptance gate |
| --- | --- | --- |
| 1 Git implementation + <=3 commands | existing `.git`, `requirements.txt`, `README.md`, `app/`, `tests/` | G1 provider CLI now; final local FastAPI interface and clean run G4/G5 |
| 2 <=2-page design note | `docs/design_note.md` and rendered output | state, approval, recovery, memory, trace excerpt, 100x bottlenecks, G5 |
| 3 Generated eval table | `artifacts/evals/results.csv`, `results.json` | emitted by offline grader with source/seed/run IDs, G4 |
| 4 Three actual bugs | `docs/three_real_bugs.md` | preserve genuine red output, fix, regression, revision; never fabricate to fill quota, G5 |
| 5 End-to-end timeout trace | `artifacts/traces/timeout_after_success.jsonl` | provider + controller + approval + reconciliation, annotated in design note, G5; G1 receipts are not this trace |
| 6 3-5-minute demo | `docs/demo_script.md`, recording/link receipt | actual side-by-side chat/trace, booking and handled fault, G5 |

## G1 contract and exact tests

`ProviderMock` exposes exactly the eight employer methods (constructor context is
not a tool):

```
search_providers(service, area, date_range)
get_provider(provider_id)
list_bookings(user_id)
hold_slot(provider_id, slot)
book(hold_id, idempotency_key)
get_booking_status(idempotency_key)
cancel(booking_id, idempotency_key)
reschedule(booking_id, new_slot, idempotency_key)
```

`app/storage.py`: WAL SQLite, FK constraints, busy timeout, short `BEGIN IMMEDIATE`
transactions. Persist provider fixtures/slots, holds, bookings, operation payload
hashes/results/faults; partial unique index on active provider/slot. Never reset
on startup. Constructor fixture seed/config are persisted and mismatches rejected.
`fixtures.py`: synthetic plumber/electrician/AC providers, variation and malicious
review; configurable quote drift. `scenario_engine.py`: stable SHA-256-derived
uniform draw by fixture seed, scenario ID and operation key: 70% success, 15%
slot_taken, 7.5% each timeout branch. Forced scenarios only constructor test config.
Injected aware clock; fixed tests at 2026-11-01T09:00:00+05:30; exact 600-second TTL.

`tests/test_provider_contract.py`: signature/output assertions; search filtering
and 3-8 options; malicious reviews; quote drift/TTL; hold collision/expiry;
book_success/slot_taken/hold_expired/both timeout branches; committed truth before
timeout; same-key replay and changed-payload/cross-action rejection; cancel 503
then same-key success after restart; reschedule success/configured and occupied
conflicts; user-scoped reads/writes; SQLite FK/WAL/active uniqueness; simultaneous
holds and competing connections; actual fresh-process persistence; statistical
smoke over stable seeds separate from deterministic fault tests.

## Frozen assumptions and dependencies

Per canonical C1: cancel/reschedule original verified price or explicit
`price unavailable from provider contract`; no invented fees. Server-established
user context will own provider instance; fixed write signatures have no user arg,
so capture user ID in constructor and enforce booking/hold/key ownership. This is
mock infrastructure, not real authentication. Dates are aware ISO timestamps in
IST; explicit `{start, end}` date range. No model, orchestration, memory or browser
implemented in this pass. New interpretations are recorded in `DECISIONS.md`.

Runtime G1 uses Python 3.11+ stdlib only. Pin pytest for tests; PDF inspection uses
already installed pypdf, not an application dependency. Future FastAPI/Pydantic/
Uvicorn added only with G4 code. Initial README three commands: install requirements,
run pytest, run read-only local provider inspection CLI (`python -m app.provider_mock`).
Final three-command interface replaces inspection with Uvicorn per canonical J2.
Store exact command output/errors and JUnit XML in `artifacts/receipts/`; generate
SHA-256 manifest and `docs/actual_progress.md` after executing checks.

## Evidence-driven G1 adjustment

Pytest installation stalled in this restricted environment. ADR-003 records the
stdlib unittest execution choice (suite remains pytest-discoverable). Actual
README initial commands are `python scripts/check_contract.py`,
`python -m unittest discover -s tests -v`, and `python -m app.provider_mock`.
Optional pytest remains pinned; no successful pytest run is claimed. Receipts
use raw unittest output plus JSON/source snapshots instead of JUnit XML.
