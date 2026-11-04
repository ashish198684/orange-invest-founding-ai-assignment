# Orange — local home-service concierge

The accepted local release runs a browser chat, PostgreSQL, two authenticated HTTP replicas, two durable
workers, an independent mock provider service and a local OpenTelemetry receiver.
Models propose constraints; persisted code controls approval and provider effects.
The browser shows actual quotes, separate approval cards, appointments, memory
controls and live traces. Offline interpretation is the default; a separately
selected Groq adapter proposes constraints without action authority. G4 evidence
and CTO acceptance are separate. The employer-facing G5 package includes a real 3:49 browser recording and source-bound evidence; **email delivery is not yet confirmed**. The repository is sponsor-approved public. The current-release OBS video and hosted link are pending.

Prerequisites: Docker Desktop with Linux containers and Docker Compose. From a
clean checkout, the three primary commands are:

```text
docker compose --project-name orange-review up -d --build --wait
docker compose --project-name orange-review exec -T api python -X utf8 scripts/g4_checks.py --label my_check
docker compose --project-name orange-review down
```

Use a new label for each run; evidence is never overwritten. The second command
checks the pinned source contract, 65 original SQLite regressions, 39 real
PostgreSQL/HTTP/process G3X checks, 28 scripted-user HTTP evaluations and offline
Groq adapter defenses. Image/dependency download is needed on first
build. The stack binds only localhost: gateway 8080, API replicas 8081 and 8082.
Open **http://127.0.0.1:8080/** after the first command. `/health` is the readiness
endpoint. These checks make no live LLM calls. Providers/payments are mocked and
telemetry stays local. The live mode contacts Groq only when explicitly selected.

The synthetic calendar is finite and persists. Tests consume slots and intentionally
crash/restart the provider; run them in a fresh named review realm, separate from
an active demo. For a second independent run use a new project name consistently
in the same three commands (for example `orange-review-2`), preserving old ledgers.
If another realm owns ports 8080–8082, shut it down without removing its volumes.

Synthetic accounts: alice / demo-alice, bob / demo-bob. These are public local
test fixtures, not production credentials. POST /login with JSON username
and password plus Origin http://127.0.0.1:8080 returns an HttpOnly SameSite session
and CSRF token. Mutation requests require that cookie, Origin and X-CSRF-Token.
GET /approvals/<id> issues an immutable session-bound card; explicit POST to
/approvals/<id>/confirm queues the approved operation and returns pending with a
stable operation ID. GET /operations/<id> reports authoritative verified outcome
or truthful unknown. API issuance is not proof that a human understood a card;
retained Chromium tests check rendering, corrections and explicit clicks.
HTTPS/OIDC and production identity are not claimed.

Try “Find a plumber in Koramangala this week, mornings only, under ₹1,800.” The
fixtures support plumber/electrician/AC servicing in Indiranagar/Koramangala with
a seven-day calendar seeded once. Select a slot to see its actual hold quote;
the separate approval button authorizes that exact action. Reload/reconnect uses
the same workflow and operation. Appointment controls issue fresh cards for
cancel/reschedule. Only verified provider readback produces success.

## Employer submission — evidence and live recording

All six requested deliverables are indexed in [SUBMISSION_INDEX](docs/submission/SUBMISSION_INDEX.md). The [verified two-page A4 design note](docs/submission/ARCHITECTURE_DESIGN_NOTE.pdf) ([Markdown source](docs/submission/ARCHITECTURE_DESIGN_NOTE.md)) explicitly covers the first 100× scaling bottlenecks and includes the real timeout-after-success trace excerpt. The [generated 28-scenario evaluation table](artifacts/evals/results.csv), [three real bugs](docs/submission/THREE_BUGS.md), [unaltered trace](artifacts/traces/timeout_after_success.jsonl) with [annotation](docs/submission/TIMEOUT_TRACE_ANNOTATION.md), and [authentic 3:49 Groq-powered Chromium walkthrough](artifacts/demo/g5_submission_demo_20261103b_groq_PASS.webm) are preserved. The video features real browser interactions with the same API/provider services and adjacent live trace. The browser-facing explanatory captions are marked as recording annotations.

The GitHub submission repository is sponsor-approved **public**. The detailed OBS script is in docs/submission/OBS_RECORDING_SCRIPT.md. The existing 3:49 WebM records historical G4 source; the sponsor will record the accepted current release manually. This is a late-prepared package, **not proof that the employer has received it**. No remote deployment or production availability is claimed.

## Separate live Groq demonstration

An ignored local `.env` may contain `GROQ_API_KEY` and
`GROQ_MODEL=openai/gpt-oss-20b`. Compose injects these into API replicas only;
the key is excluded from the build context, browser, traces and repository. Keep
the ignored file and expanded Compose configuration private. A configured key
does not establish connectivity. Select **Groq · Live** for the next chat message;
the badge changes to verified only after an actual validated response. Failures
leave the plan unchanged and explicitly unavailable, without a hidden fallback.

The adapter uses nonstreaming strict JSON Schema output and independent semantic
validation, a killable deadline, fresh context and revision checks. It receives no
user identity, approval IDs, operation keys, raw history or provider reviews.
It cannot grant consent, call provider writes, mutate memory or establish success.
Only the latest request and permitted current constraints go to Groq.
Changed facts require source evidence from that message. Recognized relative
dates, morning limits and numeric/spelled budgets are checked in code; unsupported
proposed additions are discarded and safely identified in the trace. This does
not establish perfect natural-language understanding; review the displayed plan.

The separately invoked `scripts/g4_live_smoke.py --label <new_label>` runs inside
the API container. It verifies the model catalog, three real model turns, a one-fact
correction, code-enforced consent, an actual quote and timeout recovery. It is never
part of `g4_checks.py`. Returned usage/latency are recorded; unavailable cost is null.
This is an integration sample, not a general model reliability score.

## Evidence

`/state/receipts/<label>` retains commands, exits and raw results. The check command
generates `/state/evals/<label>/results.csv`, `results.json` and the unmodified
`timeout_after_success.jsonl` worker run. Related API runs, approval snapshot and
independent SQL are retained in E12. Copy evidence out with Compose `cp` when
needed; artifact collection is not an application setup step. Browser QA uses
`scripts/g4_browser.py` with a local Playwright installation and saves actual
screenshots/events, without generating a G5 video.

Named Docker volumes retain ledgers and receipts across shutdown/restart. Startup
does not reset bookings, keys, approvals or user memory. Copy evidence from
api:/state/receipts/<label> using Docker Compose's cp command. Runtime secrets
are generated inside the runtime volume, never committed. Compose's local SQL
passwords are synthetic fixtures; do not expose this configuration publicly.

Memory is user-scoped, provenance-tagged and versioned. Inferences require explicit
confirmation and expire after one day; expired provisional values are suppressed
on every read and nulled during the user's next memory mutation. Forget immediately
nulls the operational value and retains only a versioned tombstone and event hash.
Fresh retrieval plus revision checks discard in-flight stale search/hold results.
There is no process memory cache or audit-to-context fallback. Explicit transaction
approvals remain separate business records, not long-term preference retrieval.

Sanitized traces retain hashes, counts, versions and statuses, never raw chat,
passwords, keys, reviews or preference values. Local audit metadata/tombstones are
retained until the operator removes the synthetic dataset; they cannot re-seed
memory. Generated test artifacts contain synthetic fixture state. This is logical
deletion/suppression, not forensic erasure of PostgreSQL MVCC pages or backups.
Old backups are restricted local evidence and must not be restored operationally
without reapplying deletion suppressions. No real personal data is permitted here.

The original standard-library SQLite baseline remains runnable without Docker:
python scripts/check_contract.py and python -m unittest discover -s tests -v.
Its 65 tests are distinct from G3X conformance and G4's user-agent evals.
Exactly eight provider signatures remain unchanged; constructor-only faults are
test infrastructure and are not customer-controlled routes.

See [the authoritative canonical](CANONICAL.md), [decisions](DECISIONS.md),
[G3X test map](docs/g3x_traceability.md), and source-bound receipts in
artifacts/receipts/. Actual evidence determines gate status. Nothing here claims
100× throughput, production high availability or completion of employer delivery. Current G6 engineering acceptance and delivery status are in CANONICAL Section X; Sections U and V preserve earlier acceptance records.
