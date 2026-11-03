# G4 CTO handoff - engineering pass, acceptance pending

Stopped at G4. G5, video, push and submission have not started.
The canonical deadline of 2026-11-03 14:00 IST elapsed during verification; no submission was made.

Working local app: http://127.0.0.1:8080/ . Synthetic login: `alice` / `demo-alice`
or `bob` / `demo-bob`. Current preserved demo project: `orange-g4-demo-b6d4bb72`.
Offline mode is default; select Groq Live explicitly. Providers and payments are mocks.

Runtime source commit: `b6d4bb72e5108e691fe38d1dfc994cf7dae8771c`. Clean checkout: `8a7754010e1865e2660f255e403ddca9294c36c0`.
BUILD_INFO binds 64 runtime/config/test source files to committed bytes.
The clean checkout contains no `.env`. README's three primary commands were actually
executed with a fresh project and `--require-committed`; all exited 0.
Exact commands, exits, timings and source hashes are in
[the release receipt](../artifacts/receipts/g4_release_20261103e/receipt.json) and
[command log](../artifacts/receipts/g4_release_20261103e/commands.json).

| Executed proof | Passed | Skipped |
| --- | ---: | ---: |
| Original SQLite regressions | 65 | 0 |
| PostgreSQL/HTTP/process regressions | 39 | 0 |
| Scripted-user real HTTP evaluations | 28 | 0 |
| Offline Groq adapter defenses | 20 | 0 |

Groq authentication/catalog returned HTTP 200 and listed `openai/gpt-oss-20b`.
Three actual structured turns retained a complex request, one-fact correction and
proposal-only no-change intent: 758.254 ms, 914/216 input/output tokens; 923.846 ms, 984/196 input/output tokens; 959.746 ms, 989/160 input/output tokens. Cost is unknown/null.
The live browser supplied two further real completions. This is a small integration
sample, not a model reliability benchmark. Earlier HTTP 400 schema failures and a
discarded morning constraint are preserved; complete-key prompting and source
grounding address those observed defects, with explicit unavailable behavior retained.

Chromium exercised real login/chat, malicious review display, quote drift, old-card
invalidation, separate approval, truthful timeout-after-success recovery, reload,
memory correction/forget, reschedule, cancel, mobile layout and logout.
[Screenshots and events](../artifacts/receipts/g4_release_20261103e/browser/receipt.json)
match [independent SQL/raw-trace/OTel reconciliation](../artifacts/receipts/g4_release_20261103e/audit/receipt.json).
Two provider booking records were independently inspected: the live smoke booking
remains booked; the browser booking was rescheduled and cancelled through three
separately granted operations. Exact fingerprints, prices, slots and tombstones agree.

[Generated eval CSV](../artifacts/evals/results.csv),
[JSON](../artifacts/evals/results.json), and
[unaltered timeout worker trace](../artifacts/traces/timeout_after_success.jsonl)
come from the final execution. E12 retains the related API runs and SQL snapshot.
[Engineering handoff receipt](../artifacts/receipts/g4_final_20261103/receipt.json) and
[SHA-256 manifest](../artifacts/receipts/g4_final_20261103/sha256.json) bind the evidence.
All earlier G4 failure receipts remain in artifacts/receipts/g4*.

Fixed observed defects include dropped UI clicks, stale memory during context
construction, RPC startup consuming deadlines, premature recovery-claim exhaustion,
Groq schema/grounding failures and logout using a forbidden DELETE. Logout now
expires the session without expanding SQL permissions; independent SQL verified
[the expired session](../artifacts/receipts/g4_logout_verified_20261103.json).

Known limits: synthetic finite calendar; local fixture authentication rather than
production OIDC/TLS; two supported areas and three services; bounded language
extraction rather than universal understanding; no production throughput/HA claim.
Reviews are excluded from remote intent context, not proof of general injection
immunity. Deletion suppresses operational memory and retains tombstones, not forensic
erasure of database pages/backups. Real model failures remain explicit and do not
authorize provider effects. Existing test/development volumes are preserved.
