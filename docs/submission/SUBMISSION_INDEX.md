# Orange Invest — Founding AI Engineer | Submission Map

**Prepared on 3 November 2026, after the employer's requested 2 PM deadline.** All provider APIs, payments and accounts are synthetic. The live Groq path is a controlled supplementary demonstration; the evaluator itself is offline.

## Start here

- **Local run:** [README](../../README.md) — three tested commands for a fresh Docker Compose checkout.
- **Technical design, maximum two pages:** [ARCHITECTURE_DESIGN_NOTE.md](ARCHITECTURE_DESIGN_NOTE.md). Describes explicit state, signed/immutable approval, provider idempotency, timeout recovery, memory lifecycle, traces and a measured-gates plan for 100× demand.
- **Generated evaluation table:** [results.csv](../../artifacts/evals/results.csv), [results.json](../../artifacts/evals/results.json). 28/28 deterministic HTTP scripted-user scenarios with independent SQL/trace assertions; not live-model evals.
- **Three real defects with red receipts and fixes:** [THREE_BUGS.md](THREE_BUGS.md).
- **Unaltered timeout-after-success run:** [timeout_after_success.jsonl](../../artifacts/traces/timeout_after_success.jsonl), interpreted in [TIMEOUT_TRACE_ANNOTATION.md](TIMEOUT_TRACE_ANNOTATION.md) and excerpted in the design note.
- **Authentic 3:49 screen recording (1440×900, VP8 WebM):** [Download the real browser walkthrough](../../artifacts/demo/g5_submission_demo_20261103b_groq_PASS.webm) and inspect [recording receipt / chapters](../../artifacts/demo/g5_submission_demo_20261103b_groq_receipt.json). No fake browser responses. Shows real Groq proposal, chat/trace side by side, exact approval, provider timeout recovered to one booking, reload, memory, reschedule, cancel and logout. Optional captions are explicitly marked *RECORDED DEMO ANNOTATION*. This file is hosted in GitHub, not yet on Loom or unlisted YouTube.

## Source-bound engineering proof

- Final G4 receipt: [g4_final_20261103/receipt.json](../../artifacts/receipts/g4_final_20261103/receipt.json).
- Full clean-checkout release: [g4_release_20261103e/receipt.json](../../artifacts/receipts/g4_release_20261103e/receipt.json).
- Independent SQL/trace audit: [audit/receipt.json](../../artifacts/receipts/g4_release_20261103e/audit/receipt.json).
- Real browser receipt: [browser/receipt.json](../../artifacts/receipts/g4_release_20261103e/browser/receipt.json).
- Separate live Groq smoke: [live/receipt.json](../../artifacts/receipts/g4_release_20261103e/live/receipt.json).
- Source business logic commit: `b6d4bb72e5108e691fe38d1dfc994cf7dae8771c` (BUILD_INFO locks 64 runtime files); final artifact packaging is committed subsequently.

## Quantified results (scope matters)

| Evidence | Result |
| --- | --- |
| Original SQLite suite | 65 / 65 PASS |
| Distributed PostgreSQL/HTTP/process suite | 39 / 39 PASS |
| Offline scripted-user, end-to-end HTTP scenarios | 28 / 28 PASS |
| Offline Groq adapter semantic/transport defenses | 20 / 20 PASS |
| Separate Groq integration | 3 actual model turns; 2 additional browser calls; identity and traces verified |
| Independent provider SQL/trace reconciliation | PASS; one verified live-smoke booking, one browser booking rescheduled and cancelled |
| Secret scan | PASS across final G4 evidence; fresh publication scan required before making repo public |

**Limits:** local synthetic users/providers, no real payments, no production OIDC/TLS/HA, two areas and three services, fallible real LLM, and operational rather than forensic memory erasure. The two-worker 100-active-workflow tests are not evidence of 100× sustained throughput.

## Reviewer discussion prompts

**What was assumed?** Model availability is not guaranteed; scripted evaluations should not depend on it. Local replicated workers are not production HA.

**What looked correct but was not?** Timeout ≠ failed booking; Groq strict JSON mode still produced intermittent invalid completions; logout DELETE was forbidden despite happy-path success; a browser busy flag silently dropped clicks.

**What is defensible?** Separate human approval and deterministic authority; immutable quote-bound consent; stable keys, status-first reconciliation and bounded recovery; versioned memory with forget guards; raw traces and independent provider DB results; preserved failing receipts and reproducible regression tests.

**Submission access:** the GitHub repository is initially private under `ashish198684`. The employer must be invited by GitHub username, or the sponsor must explicitly authorize public visibility. A repository URL alone does not grant private access.
