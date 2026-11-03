# G3X engineering handoff ? CTO acceptance pending

**Technical checks: PASS. Employer submission: NO-GO. STOPPED after G3X.**

The authoritative master is CANONICAL.md, ORANGE-FOUNDINGAI-20261102-003. This file indexes executed evidence and introduces no engineering instruction. No G4/G5/Groq work, push, cloud deployment, real provider or payment was performed.

## Source and exact commands

- Implementation: b3e8579dc3d41b016740fef5e81c481560c019dd.
- Clean checkout verified: 736ba3a4eb73a223171fa1e33b7ab4c1019787ab.
- Initial V3 governance: a8a4e5ebd961aefaa8ba0e130c9e2a7cc6d8cf8e. Earlier SQLite G1/G2 commits and all historical receipts remain preserved.
- Full commands, timestamps, stdout/stderr and exits: [first release](../artifacts/receipts/g3x_release_pooled_20261102/commands.json), [same-image repeated load](../artifacts/receipts/g3x_repeat_load_20261103/commands.json). Required commands exited 0.
- [Independent audit](../artifacts/receipts/g3x_final_20261103/receipt.json), [source/SQL/trace evidence hashes](../artifacts/receipts/g3x_final_20261103/sha256.json), [final canonical/deployment receipt](../artifacts/receipts/g3x_final_20261103/closeout.json).

Clean worktree used these three primary commands, with artifact copying as separate evidence collection:

```text
docker compose --project-name orange-proof-d45f5983 up -d --build --wait
docker compose --project-name orange-proof-d45f5983 exec -T api python -X utf8 scripts/g3x_checks.py --label clean_source
docker compose --project-name orange-proof-d45f5983 down
```

65/65 original SQLite tests and 39/39 actual PostgreSQL G3X tests passed, zero failures/errors/skips. These are not G4 E01?E28 user-agent evaluations. The clean-checkout source validator confirmed the exact implementation SHA. Tests include actual worker crashes, independent provider death after commit, zombie fencing, duplicate redelivery, cancellation 503, reschedule conflict/success, exact quote/approval, session/CSRF/isolation, unavailable/wrong-slot readback, memory correction/forget, hard call bounds and trace redaction.

## Running implementation

Local Compose: PostgreSQL 16; two API replicas; two outbox workers; independent eight-method provider RPC with its own schema/role/transaction; gateway; local OTLP receiver. Only localhost 8080/8081/8082 are published. PostgreSQL operations, approval snapshots, jobs and keys are durable. Approval and outbox enqueue commit together; no database transaction waits on a model/provider RPC. Every mutation uses the persisted approval, stable key and authoritative readback.

Memory uses fresh scoped retrieval, provenance, explicit inference confirmation, one-day provisional TTL, versioned correction and value-nullifying forget tombstones. Revision checks discard stale in-flight search/hold results. Pooling reuses bounded role/database connections and clears transaction-local identity on commit/rollback. Wrappers enforce model <=8, tools <=16 and killable external waits; user requests have an 18-second internal budget under the 20-second response contract. Durable recovery is separate: <=3 mutation attempts, <=6 claims, 5-minute recovery deadline and truthful unknown/dead-letter outcomes.

## Measured workload ? seed 20261101

Each experiment began with zero workflows/bookings in a fresh isolated volume. All 100 workflows were created in one simultaneous HTTP burst. Preparation was limited to six journeys at a time, with two actual execution workers. This is 100 active intents, not 100 simultaneous provider mutations or 100x throughput.

| Run | Active workflows | Elapsed s | Responses/s | HTTP p95 / max s | Full-workload journey p95 s | Queue p95 s |
|---|---:|---:|---:|---:|---:|---:|
| A / 1 | 1 | 8.798 | 0.114 | 0.106 / 3.056 | 8.770 | 0.127 |
| A / 100 | 100 | 272.650 | 0.367 | 6.846 / 17.042 | 264.156 | 1.586 |
| B / 1 | 1 | 4.703 | 0.213 | 1.075 / 1.132 | 4.702 | 0.050 |
| B / 100 | 100 | 194.824 | 0.513 | 4.511 / 10.400 | 189.989 | 1.738 |

100-workflow A: 68 BOOKED, 12 NEEDS_REAPPROVAL, 4 OUTCOME_UNKNOWN, 8 preapproval tool timeouts, 8 slot_unavailable. B: 74 BOOKED, 12 NEEDS_REAPPROVAL, 4 OUTCOME_UNKNOWN, 10 slot_unavailable. Each rejected 20 cross-user read/write attacks. Independent SQL found zero duplicate slots, duplicate logical intents, missing approvals or payload/quote mismatches. Each observed two workers and a sampled peak of four pending jobs. Each retained eight mutation retries; unknowns were reported without minting a fresh key.

Separate duplicate experiments: 100 confirmations each, all HTTP 200, one operation and one verified booking. A p95/max 5.137/5.473 seconds; B 2.444/2.545 seconds. The 69 and 75 provider-booking rows in the two final snapshots include the extra duplicate experiment booking.

Docker reported 12 CPUs and approximately 8.12 GB RAM. Limits: PostgreSQL 2 CPU / 768 MiB; other services 1 CPU / 384 MiB each. Sampled 100-workflow API peaks were 231.2 MiB (A) and 203.3 MiB (B); PostgreSQL 135.3/138.4 MiB. Full per-service CPU/memory samples and derived peaks are in the raw resource files and audit. Process isolation/CPU contention and bounded preparation limit capacity. Two runs, shared hardware and one-item baselines cannot establish a production SLO or five-year scalability superiority.

## Independent outcome and recovery inspection

- Every provider booking in both measured snapshots matched a granted immutable approval, user, provider, slot, actual quote and fingerprint. Customer BOOKED results were checked against provider SQL.
- Clean timeout-after-success case: one booking, one committed operation; explicit provider_timeout followed by authoritative booked status and truthful BOOKED exit. Quote/card/provider state agree.
- Zombie case: two claims/generations, stale_worker_fenced exit, one provider booking and one committed operation. Fencing did not replace provider idempotency.
- Forgotten preference: operational value null; future replica/process context excludes it; stale replay rejected. Raw preference/credential sentinels were absent from retained JSONL and OTLP data.
- Native pg_dump/pg_restore restored authority to a disposable database while the provider adapter stayed on its original independently committed live ledger. Reconciliation and duplicate delivery returned the same booking ID, one effect. Versions 1/2/3 reapplied without changing the key. Empty disposable schema rollback/rebuild passed; this does not prove a destructive live downgrade or every future version migration.

Clean proof retained 207 JSONL files, 705 events and 644 exported OTLP spans. Per-run schema includes timestamps, workflow/trace IDs, safe argument/result summaries, durations, approval/key hashes, state transitions, counts, versions and final reasons. Unavailable token/cost metrics remain null. OTLP is bounded best-effort: an exporter timeout was observed and retained; no lossless-transport claim is made. Durable JSONL is the retained operational evidence.

## Actual failures, assumptions and corrections

| Finding | Preserved red evidence | Correction / verified result |
|---|---|---|
| Green provider/core tests did not prove HTTP authorization classification | g3x_first_complete_20261102: 20/21, forbidden returned 409 | Correct 403 mapping; final authenticated API tests pass |
| Exhausted poison claims remained READY | g3x_poison_red_20261102 | Migration V2 dead-letters exhausted work and records truthful OUTCOME_UNKNOWN; final test passes |
| No memory cache was assumed sufficient for forgetting | g3x_inflight_forget_red_20261102 | Revision barriers reject an in-flight stale search or approval; final tests pass |
| A semaphore was treated as a connection pool | g3x_release_rehearsal_20261102: 43/100 creations; retry 69/100, zero bookings in both failed bursts | Shared transaction reads, reusable bounded connections and honest capacity/auth error separation; two fresh 100/100 bursts pass |
| Installed telemetry was mistaken for complete traces | Earlier raw traces lacked explicit provider timeout and an intermediate build label was stale | Complete schema, explicit errors/durations, credential redaction and source-hash-validated build attribution; final committed clean proof passes |

All failed outputs and source snapshots are retained. The intermediate stale BUILD_INFO label is explicitly corrected by the g3x_pool_milestone_20261102 erratum; use those receipts per-file source hashes, not the old embedded label. Final clean proof validates b3e8579 against its manifest. No historical G0/G1/G2 receipt was modified.

## Remaining limits and stop decision

Defensible: exact authenticated consent records, independent provider commit/readback, stable-key recovery, no observed duplicate/unauthorized effects, cross-replica forget, bounded requests and source-bound empirical evidence. Not defensible: 100x throughput, production identity/HA, lossless OTLP, forensic deletion of MVCC/backups, human perception from API card issuance, or 39 completed employer agent evals.

Capacity failures and four honest unknown outcomes per 100 remain visible. Privacy deletion is operational suppression/nulling, with minimal audit hashes retained; old backups need deletion suppressions before operational restoration. The actual browser, 15+ offline scripted-user evaluations, live Groq adapter, final design/video/submission package remain G4/G5. The complete assignment remains NO-GO.

**STOPPED after G3X. CTO adjudication and a separate sponsor dispatch control all later work.**
