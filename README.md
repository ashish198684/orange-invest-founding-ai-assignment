# Orange Invest — local deterministic booking core

The G3X candidate runs PostgreSQL, two authenticated HTTP replicas, two durable
workers, an independent mock provider service and a local OpenTelemetry receiver.
Models propose constraints; persisted code controls approval and provider effects.
The browser interface, Groq integration, employer end-to-end evaluations and final
video are later gates. The complete assignment is **not ready for submission**.

Prerequisites: Docker Desktop with Linux containers and Docker Compose. From a
clean checkout, the three primary commands are:

```text
docker compose up -d --build --wait
docker compose exec -T api python -X utf8 scripts/g3x_checks.py --label my_check
docker compose down
```

Use a new label for each run; evidence is never overwritten. The second command
checks the pinned source contract, all 65 original SQLite regressions and the real
PostgreSQL/HTTP/process G3X tests. Image/dependency download is needed on first
build. The stack binds only localhost: gateway 8080, API replicas 8081 and 8082.
There is no browser UI yet; /health is the readiness endpoint. The Compose
networks contain no real providers, payments, hosted telemetry or LLM calls.

Synthetic accounts: alice / demo-alice, bob / demo-bob. These are public local
test fixtures, not production credentials. POST /login with JSON username
and password plus Origin http://127.0.0.1:8080 returns an HttpOnly SameSite session
and CSRF token. Mutation requests require that cookie, Origin and X-CSRF-Token.
GET /approvals/<id> issues an immutable session-bound card; explicit POST to
/approvals/<id>/confirm queues the approved operation and returns pending with a
stable operation ID. GET /operations/<id> reports authoritative verified outcome
or truthful unknown. API issuance is not proof that a human saw a card; G4 must
test actual rendering. HTTPS/OIDC and production identity are not claimed.

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
Its 65 tests are distinct from G3X conformance and G4's required user-agent evals.
Exactly eight provider signatures remain unchanged; constructor-only faults are
test infrastructure and are not customer-controlled routes.

See [the authoritative canonical](CANONICAL.md), [decisions](DECISIONS.md),
[G3X test map](docs/g3x_traceability.md), and source-bound receipts in
artifacts/receipts/. Actual evidence determines gate status. Nothing here claims
100× throughput, production high availability or completion of G4/G5.
