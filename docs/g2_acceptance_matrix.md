# G2 test-first acceptance matrix

Order ORANGE-CTO-20261101-P1-G2-001. Tests use actual controller calls and SQLite
provider state; G1 provider tests and G2 acceptance tests are not G4 E01-E28 evals.
Initial red run precedes app/workflow.py. Controlled clock 2026-11-01 09:00 IST,
seed 20261101, constructor-controlled faults, fresh isolated DB per test.

| Invariant / order B3 | Tests in tests/test_g2_safety.py (test_ prefix omitted) |
|---|---|
| 1 Known constraints retained; missing-only questions; relative clock | missing_fields_and_correction_preserve_constraints; scripted_chat_extracts_and_preserves_without_granting; relative_saturday_uses_injected_clock; constraints_earliest_hour_and_time_window_enforced |
| 2 No approval, model says yes | absent_model_approval_and_unbound_yes_deny_all_writes |
| 3 Exact immutable approval + durable operation | exact_immutable_approval_and_operation_bindings |
| 4 Hold quote, budget, exact TTL | budget_exceeded_has_no_approvable_quote; hold_ttl_boundary_599_and_600_seconds; expired_granted_hold_does_not_execute; stale_hold_quote_tampering_denied |
| 5 Provider/slot/price/revision invalidation, ABA | changed_provider_slot_budget_and_aba_void_old_approval; stale_hold_quote_tampering_denied |
| 6 Durable logical request, repeat, concurrent confirmation | verified_booking_duplicate_confirmation_and_transport_retry; logical_request_cannot_book_second_slot_or_replace_unknown; booked_logical_request_cannot_create_fresh_booking; two_connections_concurrent_confirmations_one_booking |
| 7 Restart before/after provider side effect | restart_pending_operation_before_first_provider_write; real_process_crash_after_provider_side_effect_reconciles_first |
| 8 Timeout-after-success status-first, truthful response | timeout_after_success_status_before_any_retry_and_verified_message |
| 9 Persistent retry cap and stable key after not_found | timeout_without_booking_is_bounded_across_restarts |
| 10 Slot taken/hold expiry cannot reuse approval | slot_taken_and_provider_hold_expired_require_new_approval; hold_ttl_boundary_599_and_600_seconds |
| 11 Cancel 503 stable key, restart, read-back | cancel_503_same_key_verified_and_duplicate_safe; cancel_restart_after_503_reuses_key_and_verifies |
| 12 Reschedule conflict and verified success | reschedule_conflict_preserves_original_and_fresh_success_verified |
| 13 Identity, approval/operation ownership | cross_user_workflow_approval_and_operation_denied; provider_context_mismatch_and_client_identity_rejected; second_user_cannot_change_booking_even_with_known_id |
| 14 Untrusted reviews cannot authorize | review_injection_quarantined_no_permission_or_intent_change; absent_model_approval_and_unbound_yes_deny_all_writes |
| 15 Price unknown disclosed; price-changing action blocked | unknown_historical_price_disclosed_and_price_change_blocked; price_changing_reschedule_blocked_even_with_original_quote |
| 16 Responses agree with authoritative state under errors | timeout_after_success_status_before_any_retry_and_verified_message; unexpected_provider_error_never_fabricates_success; status_read_failure_after_commit_reports_unverified_then_recovers; cancellation/reschedule tests |

Every test optionally emits a self-contained SQLite backup, complete synthetic
DB snapshot and actual provider-call sequence when G2_EVIDENCE_DIR is set. A later
receipt runner produces machine-generated outcomes; no pass rows are handwritten.
G3 budgets/memory/full traces, G4 browser/evals, G5 submission and Groq are excluded.

Expanded adversarial cases after the first green run: fresh selection with changed
hold quote voids previous card; two users race through the real controller for
one slot; cancellation requires its own card; a fabricated success response with
no DB effect remains unknown; actual provider slot mismatch remains unknown;
expiry during status reconciliation stops without another write. The cancellation
503 restart test now kills a real child process inside the controller/provider
call, rather than relying on a direct-provider setup for that crash window.
