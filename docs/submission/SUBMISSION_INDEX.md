# Orange Invest — Founding AI Engineer | Submission Map

**Prepared on 3 November 2026, after the employer's requested 2 PM deadline.** All provider APIs, payments and accounts are synthetic. The live Groq path is a controlled supplementary demonstration; the evaluator itself is offline.

## Start here

**Current status:** G6 verified source `1eb5759` on local demo; sponsor-approved public repo. Final accepted source run recorded **65+39+28+30 = 162** passed checks, with five additional security checks, actual Groq smoke and post-release Chromium booking proof. A current-source 3–5-minute Loom/unlisted YouTube link and employer email **remain pending**. Use the [short, robust OBS script](OBS_FINAL_MINIMAL_SCRIPT.md) ([older extended plan](OBS_RECORDING_SCRIPT.md)) and [late-delivery email draft](EMPLOYER_EMAIL_DRAFT.md).

- **Local run:** [README](../../README.md) — three tested commands for a fresh Docker Compose checkout.
- **Technical design, two pages actually verified:** [ARCHITECTURE_DESIGN_NOTE.pdf](ARCHITECTURE_DESIGN_NOTE.pdf) ([Markdown source](ARCHITECTURE_DESIGN_NOTE.md)). Describes explicit state, signed/immutable approval, provider idempotency, timeout recovery, memory lifecycle, traces and a measured-gates plan for 100× demand.
- **Generated evaluation table:** [results.csv](../../artifacts/evals/results.csv), [results.json](../../artifacts/evals/results.json). 28/28 deterministic HTTP scripted-user scenarios with independent SQL/trace assertions; not live-model evals.
- **Three real defects with red receipts and fixes:** [THREE_BUGS.md](THREE_BUGS.md).
- **Unaltered timeout-after-success run:** [timeout_after_success.jsonl](../../artifacts/traces/timeout_after_success.jsonl), interpreted in [TIMEOUT_TRACE_ANNOTATION.md](TIMEOUT_TRACE_ANNOTATION.md) and excerpted in the design note.
- **Historical G4 authentic 3:49 screen recording (1440×900, VP8 WebM; NOT the required current G6 hosted recording):** [Download the real browser walkthrough](../../artifacts/demo/g5_submission_demo_20261103b_groq_PASS.webm) and inspect [recording receipt / chapters](../../artifacts/demo/g5_submission_demo_20261103b_groq_receipt.json). No fake browser responses. Shows real Groq proposal, chat/trace side by side, exact approval, provider timeout recovered to one booking, reload, memory, reschedule, cancel and logout. Optional captions are explicitly marked *RECORDED DEMO ANNOTATION*. This file is hosted in GitHub, not yet on Loom or unlisted YouTube.

## Current accepted release proof

**Current runtime:** `1eb5759772ec5d491155b43fcbc16ebf5accaa45`; build manifest commit `83d9322` binds 69 code/config/test files. Local image `orange-invest-g6:final` and browser were verified against that runtime source. The next packaging commit contains no application-source changes.

- [Current frozen release receipt](../../artifacts/receipts/g6_frozen_final_20261104/receipt.json): 65 original, 39 distributed, 28 offline E2E, 30 Groq/history/action adapter tests; five additional security/trace checks passed separately.
- [Current release browser proof](../../artifacts/receipts/g6_final_live_browser_20261104/receipt.json): zero Send disabled-state transitions during polling, followed by an exact approved booking and timeout-after-success recovery into one booking.
- [Current source Groq smoke](../../artifacts/receipts/g6_frozen_groq_smoke_20261104/receipt.json): three real model responses with measured usage/latency; not statistical accuracy certification.
- [Historical OBS preflight](../../artifacts/receipts/g5_obs_preparation_20261103/request_preflight.json): prior Groq request preserved, separate from final source/browser proof. Current user-facing demo recording still required.
- [Typed-argument raw timeout run](../../artifacts/traces/g5_timeout_after_success_typed.jsonl): a distinct retained worker execution, cross-referenced in the annotation.
- [Publication secret/history scan](../../artifacts/receipts/g5_public_delivery_20261103/secret_review.json): reachable Git history, ZIP contents, tracked files and prepared delivery files; no actual key or scanned credential/private-key pattern found. Pattern scanning does not guarantee detection of every secret format.

**Final G6 source-bound receipts:** [full runner](../../artifacts/receipts/g6_frozen_final_20261104/receipt.json), [model smoke](../../artifacts/receipts/g6_frozen_groq_smoke_20261104/receipt.json), [post-deploy browser](../../artifacts/receipts/g6_final_live_browser_20261104/receipt.json), and [raw G6 timeout trace](../../artifacts/traces/g6_frozen_timeout_after_success.jsonl). The published generated `artifacts/evals/results.csv` now has 28 PASS rows stamped `1eb5759`; previous G4/G6 output is preserved under archival filenames. A deliberately failed 9-turn live exploratory trial is preserved separately and is NOT relabeled PASS. The legacy distributed/E2E receipts retain their true `UNCOMMITTED` execution labels. [Independent byte reconciliation](../../artifacts/receipts/g5_public_delivery_20261103/source_reconciliation.json) matches every recorded application file to `ac1493e`, including frontend files in the E2E snapshot. A separately listed PDF-renderer difference is auxiliary. Receipts are not rewritten and this is not a claim of a new regression run.

## Historical G4 engineering proof

- Final G4 receipt: [g4_final_20261103/receipt.json](../../artifacts/receipts/g4_final_20261103/receipt.json).
- Full clean-checkout release: [g4_release_20261103e/receipt.json](../../artifacts/receipts/g4_release_20261103e/receipt.json).
- Independent SQL/trace audit: [audit/receipt.json](../../artifacts/receipts/g4_release_20261103e/audit/receipt.json).
- Real browser receipt: [browser/receipt.json](../../artifacts/receipts/g4_release_20261103e/browser/receipt.json).
- Separate live Groq smoke: [live/receipt.json](../../artifacts/receipts/g4_release_20261103e/live/receipt.json).
- Source business logic commit: `b6d4bb72e5108e691fe38d1dfc994cf7dae8771c` (BUILD_INFO locks 64 runtime files); final artifact packaging is committed subsequently.

## Historical G4 quantified results

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

**Submission access:** the sponsor explicitly authorised public visibility and the repository is now public. The authentic 3:49 WebM above records historical G4 source `b6d4bb7`, before the polling fix. It is not the new manual OBS recording. A current-release automatic capture stopped before provider selection after grounding rejected a service proposal; its failure is preserved and is not a passing demonstration. The exact shorter OBS prompt subsequently passed a real browser preflight. A current-release hosted video and actual employer email delivery remain pending.
