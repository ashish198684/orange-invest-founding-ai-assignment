# G3X acceptance traceability (L4 as amended by M2-M4)

This is a test map, not a competing master. CANONICAL.md governs every requirement.
Only executed receipts establish pass/fail. Existing tests/ remains the 65-test
SQLite baseline; tests_g3x/ uses actual PostgreSQL and independent provider RPC.

| Canonical invariant / graded requirement | Implementation | Executable proof |
|---|---|---|
| L2.1 authenticated identity | runtime/security.py, http_api.py, PG RLS | stale_card_revision_aba_and_identity_override_rejected; issued_card_expiry_session_expiry_and_cross_user_operations |
| L2.2 exact approvals / employer must-have 2 | workflow.py reused; issued_cards HTTP | http_card_issuance_csrf_session_and_no_alternate_mutation; exact_quote_budget_and_no_model_approval |
| L2.3-5 durable intent, independent provider, short transactions / must-have 3 | runtime/pg.py, worker.py, provider_client/server.py | boundary role tests; provider_commit_survives_rolled_back_authority_transaction; timeout_after_success_and_logical_request_deduplication; crash_before_and_after_provider_and_status_recovery; expired_worker_cannot_update_state |
| L2.6 cancellation/reschedule | original core via PgController | cancel_retry_and_reschedule_conflict_preserve_truth; unknown_price_change_fails_closed |
| L2.7 governed memory / must-have 6 | runtime/memory.py, DB tombstones/events | memory_cross_replica_forget_stale_replay_and_privacy; inferred_memory_not_applied_until_confirmed |
| L2.8 response/durable budgets / must-have 5 | Run, isolated RPC, durable attempts/claims/deadlines | actual_tool_model_and_wall_caps; timeout_without_booking_three_attempts_no_new_key; HTTP pending/polling tests |
| L2.9 untrusted output / must-have 4 | original core data wrappers; no model mutation routes | untrusted_reviews_do_not_modify_intent_or_permissions; exact_quote_budget_and_no_model_approval |
| L2.10 truth / must-have 7 | worker readback, local OTLP + sanitized JSONL | real RPC and final SQL snapshots; HTTP poll truth; budget/lease terminal evidence |
| L2.11 fixed eight methods | original ProviderMock inheritance, exact-signature RPC client | boundary exact-signature test; original 28 provider tests; PG fault/cancel/reschedule conformance |
| L2.12 attribution | code SHA/build info, source manifests, canonical journal | source-bound G3X receipts and read-only grader |
| Must-have 1 constraints/corrections | unchanged core + typed proposal adapter | 37 G2 baseline plus PostgreSQL ABA/quote tests |
| Must-have 8 offline end-to-end evaluations | G4, not authorized here | NOT_STARTED; G3X tests are not mislabelled as E01-E28 |
| Six employer deliverables | repo/README/test evidence foundation now | Final design note/eval table/annotated end-to-end trace/video remain G4/G5 gates; no completion claim |
| M2.7 load/restore | benchmark and recovery harness | Separate 1x, 100 logical workflows, 100 duplicate confirmations, SQL invariants and disposable restore measurements required in final G3X packet |
