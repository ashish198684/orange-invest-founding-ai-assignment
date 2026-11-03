# Architecture decisions — Orange Invest

## ADR-012 / 2026-11-03 — Groq extracts proposals; deterministic code composes status

- Implements canonical P2/P4, not a new orchestration layer or optional model-routing
  feature. Target is `openai/gpt-oss-20b`; the deterministic adapter stays the default.
  Only API replicas receive the ignored environment key. No new dependency is added.
- Use nonstreaming strict JSON Schema, then independent Python validation of domain,
  types, money, dates and retained time constraints. The schema has no approval,
  identity, provider-write or memory fields. No tools are supplied to Groq. Model
  refusals, malformed output, rate limits, missing credentials and timeouts fail
  explicitly without changing the plan or silently switching adapters.
- Context is freshly retrieved typed constraints. Reviews, raw history, identity,
  approval IDs and operation keys are excluded. Workflow and memory revisions are
  rechecked inside the correction transaction after the remote call. Status and
  consent copy are composed by code from actual state; model text cannot claim
  success. Existing provider hold/consent/readback paths remain authoritative.
- Official support verified against [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
  and [API reference](https://console.groq.com/docs/api-reference): GPT-OSS 20B strict
  mode is supported; this path uses neither streaming nor tool use.
- Actual first live evidence: `artifacts/receipts/g4_groq_live_first_20261103/cases/receipt.json`.
  Catalog/authentication HTTP 200, three real turns, actual returned model ID,
  latency and usage, one separately approved provider booking after timeout.
  The sample is not a general reliability score or evidence that a model is
  immune to injection. Review exclusion and deterministic write guards are the
  demonstrated defenses. Final source-bound replay remains a separate receipt.
- A new adversarial regression exposed forgetting between context retrieval and
  its initial revision capture. The original failure is retained in
  `g4_context_race_red_20261103`. Context construction now checks the memory
  revision before and after retrieval on one shared DB connection, and checks
  again before applying the returned proposal. The test uses a fake interpreter
  boundary; no forgotten preference was actually sent to Groq in that test.
- Actual live Chromium v1 exposed an over-narrow date window and an invented
  earliest hour (`g4_browser_live_candidate_20261103_screens`). Prompt/schema v2
  requires source evidence from the latest message for changed constraints.
  Recognized relative calendars and morning bounds are resolved independently
  in code; unsupported new fields are discarded and their field names recorded.
  Raw evidence spans are not logged. Regression fixtures preserve the observed
  wrong date and prevent a budget-only correction from rewriting the calendar.

## ADR-011 / 2026-11-03 — Keep hard RPC isolation with a minimal child

- Under G4's regression sequence, retained fresh-realm failures in
  `artifacts/receipts/g4_fresh_baseline_20261103/regressions/` showed timeout
  recovery exhausting the eight-second worker budget before all three permitted
  attempts. The previous multiprocessing spawn re-imported the parent worker,
  controller, PostgreSQL and telemetry modules for each individual HTTP call.
- Replace only that transport child with a minimal stdlib HTTP subprocess. The
  parent still enforces the same killable call deadline, semaphore, tool count,
  eight public signatures, trusted identity, trace propagation and same-key
  provider protocol. Secrets travel on stdin; no shell or secret command argument.
  No worker/lease/response budget is increased, and no new orchestrator is added.
- The fencing test also assumed its own `claim` must beat a legitimate live
  worker. It now verifies the winning replacement's booked result before asserting
  stale-worker rejection and exactly one provider effect. This preserves the
  tested business invariant rather than asserting a particular race winner.
- Original red receipts and source snapshots remain immutable. The complete
  65+39 suite and 28 scripted-user scenarios must pass again before Groq work.
- The faster transport exposed a second genuine recovery defect: six one-second
  unavailable-status retries could exhaust all claims before Docker restarted a
  provider that had already committed. The retained `g4_fresh_rpcfix_20261103`
  process-death case is red. Recovery now persists bounded 2/4/8/16/20-second
  delays between claims, under the existing six-claim/five-minute recovery bound.
  Write attempts, user-facing deadlines and operation identity are unchanged.

## ADR-000 / 2026-11-01 — initial CTO freeze
- **Status:** Accepted implementation baseline, NOT implementation evidence.
- **Decision:** A single deterministic workflow controller with local SQLite state, immutable user approval records, stable idempotency operations, scripted or recorded parser, optional LLM, eight exact mock tools, bounded execution, and scoped persistent preferences.
- **Alternatives rejected:** unbounded multi-agent swarm, LLM acting as authority, cloud deployment, in-memory-only booking state, direct approval from model output, arbitrary new provider APIs, full vector database for three user preferences.
- **Ambiguities:** Fixed provider outputs do not expose booking price for historical reschedule/cancel; use a disclosed `price_unknown` sentinel and approved snapshot rather than fabricate a price or fee. Exact decisions in CANONICAL C1.
- **Evidence:** Original PDF; `CANONICAL.md`; execution evidence pending.

## Template for later Codex ADRs
- Decision ID, author, date, status:
- Source ambiguity or observed failure:
- Alternatives and decision:
- Security/business consequences:
- Tests, trace and changed canonical section:

## ADR-001 / 2026-11-01 - original contract and local implementation boundary
- **Status:** Accepted; G0/G1 only in this pass.
- **Evidence:** Found `C:/Users/marke/Downloads/FoundingEngineer-Assignment.pdf`, copied unchanged to `source/FoundingEngineer-Assignment.pdf`. SHA-256 `dc74d7e214479744e998e8471e68104b7790c8845de7241c34c28dd2cfa2db7d`; pypdf observed three pages. Compared all eight tools, failure percentages, eight must-haves and six deliverables with transcription/canonical; no material contract discrepancy observed. Extraction is `artifacts/receipts/pdf_extraction.txt`. Initial cp1252 console error corrected with `python -X utf8`.
- **Decision:** Keep the existing local Git repository/history. G1 runtime is Python stdlib + SQLite; defer FastAPI/Pydantic/Uvicorn until actual HTTP implementation. No browser, parser, controller, approvals, memory or external services in this pass. Provider tools remain independently testable infrastructure; no user-facing write endpoint exists.
- **Frozen ambiguities:** Canonical C1.3 unknown historical price sentinel and C1.7 trusted server-established user identity still apply; no new price or real authentication claim.

## ADR-002 / 2026-11-01 - fixed signatures, identity, fixtures and outcome semantics
- **Ambiguity:** Fixed hold/book/cancel/reschedule signatures have no user argument; date-range shape, mock fixture domain, response envelope and replay transport behavior are unspecified.
- **Decision:** `ProviderMock(..., user_id=...)` captures trusted context outside the eight tool signatures. All holds, bookings, outcomes and reads enforce that context. Future server creates the instance; neither chat nor reviews supply it. This is local isolation, not authentication. Keys are globally unique and bind action + user + canonical payload SHA-256; changed payload or cross-action reuse rejects, another user gets forbidden.
- **Calendar:** `date_range` is `{start,end}` with aware ISO timestamps, start-inclusive/end-exclusive. Normalize to fixed IST offset; reject naive timestamps. Synthetic fixtures cover plumber/electrician/ac servicing in Indiranagar/Koramangala, three varied providers each, next seven days at 09/11/15 IST. Supported searches return three options even if no slots remain; unsupported fixture service/area returns an empty list rather than fabricated availability. No claim of unrestricted geography/calendar. Calendar persists after initial creation; restart does not roll it forward.
- **Holds:** Exclusive until the exact 600-second expiry boundary; read availability ignores expired holds; writes persist lazy expiry. Forced `slot_taken` marks the provider slot taken durably (simulated competitor), without inventing a booking for the caller. Atomic SQLite writer serialization and a partial unique index protect active bookings.
- **Responses/errors:** Dictionaries use contract fields; booking status/cancel use `status`. Typed `ProviderError(code,http_status)`; `ProviderTimeout` also subclasses TimeoutError. No actual sleeping or network faults. A successful timeout branch commits both booking and outcome before raising; identical replay returns original booking response even after hold expiry. Timeout-without-booking replays the persisted timeout and authoritative status remains not_found, requiring bounded caller recovery later. Failed outcomes replay identically. A successful response replay describes that operation; current status must still be read from status/list (e.g. after cancellation).
- **Cancel/reschedule:** First valid cancel attempt per operation key persists transient 503, same-key retry performs cancellation; later delivery replays. `get_booking_status` is for book keys only, with cancelled bookings reported failed; use list_bookings to reconcile cancel/reschedule as canonical C1.4/C1.5 require. Configured, held or booked reschedule targets conflict and preserve the original slot. No new quote/fee API.
- **Reproducibility:** Persist seed/scenario/quote delta/conflict config in DB; reject explicit mismatch on reopening. Stable SHA-256 draw by seed + scenario ID + operation key, independent of call order; forced branch/config is constructor-only test setup. UUIDs are opaque identities, not random fault decisions. Fake aware clock in tests; default real IST clock in inspection CLI.
- **Tests:** `tests/test_provider_contract.py`; receipts carry source hashes/snapshots. Provider-level isolation/uniqueness does not prove future workflow approval or logical-request dedupe.

## ADR-003 / 2026-11-01 - offline standard-library test execution
- **Observed constraint:** Python 3.12.10 is available; pytest is absent. Multiple pinned pytest installation attempts stalled with no package output, including an isolated dry-run killed by subprocess timeout after 25 seconds. No global package installation is required or claimed.
- **Decision:** Implement G1 contract tests as stdlib unittest.TestCase (also discoverable by pytest). Run `python -m unittest discover -s tests -v` offline without dependencies. Keep `pytest==8.3.5` as an optional pinned test driver in requirements.txt, not a runtime requirement. No custom imitation of pytest. Future application stack remains canonical Python/FastAPI/SQLite; this only changes G1 test execution. Do not claim pytest was executed successfully.
- **Evidence:** `artifacts/receipts/dependency_diagnostic.json`; successful unittest receipts. README initial three-command interface is contract check / offline tests / provider inspection; final Uvicorn command is deferred until G4. This avoids requiring network installation merely to test stdlib provider code.

## ADR-004 / 2026-11-01 — Human-led Codex dispatch; CTO gate adjudication
- **Status:** Accepted governance instruction from sponsor. This ADR is subordinate to the frozen employer PDF and CANONICAL.md; it records a process clarification and does not revise application requirements.
- **Roles / execution boundary:** Sponsor (human) alone authorizes and manually dispatches an engineering order to Codex. ChatGPT is CTO/principal architect: review evidence, define architecture/risks/acceptance criteria, write CTO directions and declare GO/NO-GO. Codex is founding implementation engineer: plan, write/debug code, execute tests, preserve receipts and report actual results. ChatGPT must not autonomously start, resume, or operate Codex, nor implement application code. No background task or automatic onward phase is authorized.
- **Evidence reviewed (2026-11-01):** G0 provider/employer-source receipt PASS (4 hash checks); G1 provider tests PASS (28/28, 0 skipped, exit 0) as recorded by g1_final.json, g1_final.txt, gate_status.json and docs/actual_progress.md. The Codex session launched earlier by ChatGPT exited 0. These are direct provider-layer checks only, not full controlled-agent end-to-end acceptance or E01–E28 user simulations.
- **Git status:** Original source baseline d63a1d8; G1 implementation and evidence uncommitted. The release receipt must not represent the baseline commit as the G1 implementation commit. G2–G5 are NOT_STARTED.
- **CTO disposition:** G0 accepted; G1 evidence provisionally supports functional completion but is **NOT HANDOVER-CLOSED** until Codex, after explicit sponsor dispatch, freezes a coherent commit and verifies source/receipt binding with a fresh uniquely labelled post-commit test. Preserve all three authentic bug failures and regressions; no fake bugs.
- **Frozen canonical preservation:** scripts/check_contract.py pins CANONICAL.md SHA-256. Do not silently edit CANONICAL.md, AGENTS.md, the PDF, or historical receipts. Any future substantive canonical revision requires a versioned CTO-approved change, explicit G0 source-hash update/rebaseline, and preservation of the prior evidence. This ADR documents manual dispatch without changing the pinned contract.
- **Next sponsor-dispatched bounded order (not yet authorized):** (1) close G1 via commit, clean source/receipt hashes, one fresh uniquely labelled rerun; (2) G2 safety only: persistent workflow state, exact action/provider/slot/price-or-unknown approval records and invalidation, logical-request dedupe, trusted user scope, book timeout-after-success reconciliation, same-key cancel retry, reschedule conflict and restart/concurrency safeguards. Keep approval as database authority and the model as interpretation-only. Test negative paths. Do NOT begin UI, long-term memory, optional LLM, G3/G4/G5, cloud deployment or video until later sponsor dispatches.
- **Gate acceptance rule:** CTO reviews CODE COMMIT + exact COMMAND + EXIT CODE + TESTS RUN/PASSED + SHA-256 EVIDENCE + observed DB/trace behavior. A passing provider test, attractive chat, or model declaration never proves user-approval enforcement, safe workflow, or final assignment completion.

## ADR-005 / 2026-11-01 - GroqCloud LLM provider selection (v1)
- **Status / authority:** Sponsor-approved provider selection, recorded by Codex under the documentation-only CTO directive. This ADR is a design decision, not implementation, benchmark evidence or gate acceptance.
- **Provider / endpoint:** GroqCloud; `https://api.groq.com/openai/v1`. Initial model candidate: `openai/gpt-oss-20b`; evaluation alternative: `openai/gpt-oss-120b`. Exact model selection remains subject to measured evaluation.
- **Credentials:** `GROQ_API_KEY` through environment variables only; never commit credentials or include them in traces.
- **Integration phase:** G4 only after G3 acceptance and a separate human-sponsor dispatch. G2 remains deterministic and has no LLM dependency. This instruction does not authorize G1 Git closeout, G2, Groq implementation or any subsequent phase.
- **Offline baseline:** Retain the existing scripted/recorded model approach (`ScriptedModel` / `RecordedModel`) for deterministic offline tests and reproducible evaluations. External LLM access remains off by default and is not required for offline tests.
- **Model boundary:** Use strict structured outputs for intent and constraint extraction; validate every returned field against application schemas and current workflow state. Model outputs are proposals. Deterministic Python code and SQLite control approvals, bookings, cancellations, rescheduling, idempotency and authoritative provider reconciliation. The model receives no direct mutation, approval or database authority. Governed Second Brain memory remains independent of the model and cannot establish booking truth or grant consent.
- **Acceptance:** Evaluate each candidate against the scripted baseline with measured correctness (including constraints, corrections and prompt injection), latency, failure handling and cost evidence. Record model ID, prompt version, actual token usage and latency in sanitized traces; unavailable metrics remain unknown, never fabricated. Unavailability, timeout or unusable output must fail safely. An LLM response is never evidence that a customer action succeeded.
- **Alternatives / consequences:** GroqCloud is selected instead of the Claude API for the live interpreter; neither model candidate is accepted as benchmarked. Provider choice does not change the deterministic authority model, fixed mock-provider contract, approval requirements or gate sequence.
- **Canonical compatibility / preservation:** Consistent with CANONICAL A1, B1-B2, C1.9, F3 and G2: optional interpretation adapter, offline baseline and deterministic authority. No canonical requirement is overridden. The frozen CANONICAL.md, its pinned hash, AGENTS.md, application code, tests and historical receipts are unchanged by this ADR. No integration or behavioral tests were run under this documentation-only directive. Human sponsor controls all subsequent engineering dispatches.

## ADR-006 / 2026-11-01 - P0 canonical reconciliation, Option A (v1)
- **Status / authority:** Accepted sponsor-dispatched P0 resolution only. Original employer PDF and hash-verified canonical remain authoritative; ADR-004 human-led dispatch and ADR-005 Groq selection are preserved.
- **Finding:** Git baseline d63a1d8 CANONICAL.md is an exact byte prefix of the pre-P0 working file. The only additional content is the boundary newline and 47-line CTO addendum; no other formatting or content differences were found. Baseline SHA-256 matches the existing pinned value.
- **Resolution:** Restore only CANONICAL.md to exact baseline bytes (LF, no final newline), SHA-256 2f057c7a626174dde3cc35c04a6c4082f2b55e8f49e2b92d2bda43703895b5e2. No pinned source hash is changed and no repository reset is performed.
- **Preservation:** docs/proposals/20261101_cto_addendum_NOT_AUTHORITATIVE_NOT_APPROVED/addendum_unchanged.md preserves the complete appended bytes unchanged; its README explicitly marks the proposal NOT AUTHORITATIVE / NOT APPROVED. CANONICAL_before_P0.md preserves the full pre-P0 working file, SHA-256 a5187084ff50451cc7813dcdb8a2310cdaecac0e0959d27632509278ed37d325. Historical approval language in the archived text does not grant current authority.
- **Verification / evidence:** Run the unchanged scripts/check_contract.py under the existing Python 3.12 interpreter. Exact command, actual stdout/stderr, exit code, before/after Git status, canonical diffs, preservation inventories and evidence hashes are recorded in artifacts/receipts/p0_20261101_option_a/. The generated receipt, rather than this ADR, establishes the check result.
- **Scope:** No application code, tests, historical receipts, source snapshots, AGENTS.md or assignment PDF changed. No G1 closeout, G2 work, Groq integration or onward phase authorized. Stop after P0 for CTO review.

## ADR-007 / 2026-11-02 - G2 deterministic controller, local recovery and price boundary (v1)
- **Status / authority:** Implementation interpretation under sponsor-dispatched ORANGE-CTO-20261101-P1-G2-001; CTO gate acceptance pending. Frozen canonical/PDF, eight provider signatures and ADR-004/005/006 remain unchanged.
- **Authority model:** Trusted server/test RequestContext supplies user identity; no client/model user override. ScriptedModel proposes validated draft fields only. Explicit confirm identifies the immutable pending approval. All book/cancel/reschedule calls share the persisted operation authorization gate. ProviderMock remains directly callable test infrastructure, not an approval authority.
- **State refinement (canonical D1):** COLLECTING, CHOOSING, AWAITING_APPROVAL, EXECUTING, VERIFYING, BOOKED, NEEDS_REAPPROVAL, OUTCOME_UNKNOWN, CONFLICT, CANCELLED, RESCHEDULED. Search/hold are synchronous proposal steps; they do not need separate persisted states. Explicit transition guards include VERIFYING -> EXECUTING only for a bounded same-key retry after authoritative read-back. No model sets state.
- **Durability / deduplication:** Unique (user, logical_request_id), one live/committed book operation per workflow, immutable approval/operation payloads and keys, pending change uniqueness by booking, monotonic workflow revision and a durable booking binding. Corrections/requotes invalidate pending approval including ABA. Unresolved or booked logical requests cannot create a second booking on another slot. A new logical request represents a distinct explicit customer intent, never automatic timeout recovery.
- **Concurrency / restart:** Short SQLite transactions persist permission/key before provider calls. A local kernel file lock serializes execution/reconciliation across independent processes/connections; the OS releases it on crash. The embedding server must invoke recover() before startup mutation dispatch. Pending work reconciles first even if its hold/approval later expired. No transaction waits on a provider/model. This is local coordination, not distributed exactly-once execution.
- **Retry policy:** At most three persisted mutation attempts per operation, including two same-key transient retries; restarts never replenish the count. After persistent timeout-without-booking, report OUTCOME_UNKNOWN/unverified and lock the logical request; do not fabricate success/failure or escape using a fresh key. Unknown errors and unavailable status remain unverified.
- **Price ambiguity (canonical C1.3):** Book binds actual hold quote. Cancel/reschedule show verified stored original booking price explicitly as original, or price_unavailable_from_provider_contract. New price is unavailable; the local fixed mock charges no new fees. Only a no-fee/non-price-changing mock reschedule is supported under that disclosed snapshot. Price-changing requests fail closed (price_unknown), even when original amount is known. No fabricated fresh quote/fee or added provider API.
- **Evidence / boundary:** docs/g2_acceptance_matrix.md maps executable tests to invariants; scripts/g2_evidence.py emits source-bound raw results, per-case DB backups, SQL inspection and a real timeout controller probe. This instrumentation is not the G3 tracing subsystem or G4 scripted-user evals. No Groq, memory, browser, general run budget or onward gate is implemented. Exact commits, counts and hashes live in generated receipts; actual red/fix/green history is in docs/g2_handoff.md.


## ADR-008 / 2026-11-02 — Sponsor-directed 100× local distributed architecture (canonical V2)
- **Status / authority:** Sponsor explicitly requested the 100× architecture to be implemented NOW for the assignment, and expressly required ALL future Codex engineering instructions to appear in `CANONICAL.md`. This ADR records the decision; it contains no independent engineering work order and does not dispatch Codex.
- **Canonical revision:** `ORANGE-FOUNDINGAI-20261102-002` is current. Previous original `ORANGE-FOUNDINGAI-20261101-001` preserved byte-for-byte in `docs/canonical_history/CANONICAL_ORANGE-FOUNDINGAI-20261101-001_FROZEN.md`, SHA-256 `2f057c7a626174dde3cc35c04a6c4082f2b55e8f49e2b92d2bda43703895b5e2`. Current v2 SHA-256 `32be62a2ec8330328ef57ad5110cbe23a63a84e8f59908aa2355324796115153` and versioned G0 verifier includes both versions; old employer PDF/AGENTS/transcription hashes remain unchanged. All prior G0/G1/G2 receipts remain historically valid for the source they tested; none certifies v2 infrastructure.
- **Decision:** Build and test a LOCAL Docker Compose runtime now using PostgreSQL as shared durable authority; two or more API and worker instances for concurrency proof; PostgreSQL transactional outbox/leased and fenced worker claims; verified local demo-user login/session and per-route authorization; OpenTelemetry-compatible trace correlation plus sanitized JSONL; memory and hard budgets. Exactly eight original mock provider methods/faults remain immutable. Scripted or recorded offline evaluations and the <=3-command README remain mandatory. No cloud, real providers, payments, remote authentication provider or hosted telemetry.
- **Alternatives rejected for this deadline:** SQLite-only deployment as final 100× implementation (preserve as regression baseline); introducing Temporal, Step Functions, Redis/Kafka, Kubernetes, cloud OIDC or independent multi-agent swarm without an empirical need. The Postgres outbox is the chosen durable orchestration component; it is NOT an assertion of exactly-once network calls or measured 100× throughput.
- **Risk / transparency:** Higher dependency/implementation risk vs initial local-only minimal plan, with potential to delay employer mandatory deliverables. Tests must demonstrate that the new stack remains locally runnable and no less safe than the accepted G1/G2 foundation. If migration, authentication, hard wall deadline or 100× proof fails, report objective NO-GO and stop; no fake pass or silent fall back. Only human sponsor may authorize next-phase execution; Codex's next bounded order is Section L4 of CURRENT `CANONICAL.md`.
- **Source evidence at decision time:** Sponsor direction, original three-page assignment PDF, prior committed source/evidence; Docker Desktop engine observed accessible with 12 CPUs and approximately 8 GiB at the last inspection. No PG API/worker/OTel/auth implementation is claimed as complete by this ADR. Architecture quality is judged by independent tests and captured DB/trace state, consistent with Anthropic effective agents and AWS Agentic AI Lens.


## ADR-010 / 2026-11-02 — Reuse tested core and minimal HTTP transport for G3X
- **Scope:** Implementation rationale under canonical B's alternative-minimal-stack allowance. No new dispatch, model authority or gate expansion.
- **Decision / evidence:** Keep the original WorkflowController and eight ProviderMock signatures behind a narrow psycopg repository and independent RPC adapter. Actual 65-test SQLite regressions have remained green while PG process/HTTP tests exercise the same business code. Use Python's standard-library HTTP transport for this bounded local JSON API instead of introducing FastAPI/Pydantic/Uvicorn during G3X. This reduces added runtime dependencies; typed domain validation remains in the reused core. It is not a claim of superior general HTTP performance or production server hardening.
- **Tradeoff / limits:** Routing and explicit field checks are manually maintained, with executable session/CSRF/card/auth tests. Hard model/provider isolation adds process-launch overhead, measured by the release benchmark. G4 must still implement and test browser rendering and the complete conversational journey; current API receipts cannot prove human perception. The Docker local-only boundary and original grader contracts are unchanged.

## ADR-009 / 2026-11-02 — Five-year architecture investment review, Canonical V3
- **Authority / status:** CTO review of the sponsor's request to challenge whether the 100×-now design is genuinely best for a locally runnable employer assignment. Current architecture decision and **all subsequent Codex engineering instructions are in `CANONICAL.md` Section M as amendments to Section L4**, not in this ADR or chat. No Codex execution authorized by this entry.
- **Governance:** Current canonical is `ORANGE-FOUNDINGAI-20261102-003`, SHA-256 `6784499e9e0ac56d26eabac6d34036076890cdbda299da213de32dcd290cc98a`. Original V2 preserved byte-for-byte at `docs/canonical_history/CANONICAL_ORANGE-FOUNDINGAI-20261102-002_FROZEN.md`, SHA-256 `32be62a2ec8330328ef57ad5110cbe23a63a84e8f59908aa2355324796115153`; V1 separately archived and pinned. Employer PDF, AGENTS and original transcription hashes unchanged. Verifier checks all six files.
- **Selected architecture:** Maintain deterministic modular business authority and the 100×-now, local PostgreSQL/outbox/multiple worker/API runtime chosen in ADR-008, **conditional on evidence**. No claim of globally best architecture. Reject unnecessary multi-agent swarm, Kubernetes microservices and Temporal/Step Functions before proven need. Preserve existing SQLite 65/65 regression baseline, and evaluate PG with separate provider transaction/role/schema and failure injection.
- **Corrections earned by review:** Independent provider side-effect boundary (no shared app+provider atomic commit); honest <=20-second synchronous response plus durable pending/reconciliation contract; server-issued immutable card versus unprovable human perception; stale-lease fencing distinct from external provider idempotency; deletion/tombstone versus redacted audit retention; behavior/version compatibility and backup/restore rehearsal. See binding canonical M2–M4; earlier conflicting directions are superseded.
- **Evidence and limitations:** CTO design review uses Anthropic's simple/composable agent patterns and eval-driven development; AWS 2026 Agentic AI Lens security, reliability, audit and multi-layer testing; PostgreSQL's own `SKIP LOCKED` queue caveat. The design is a hypothesis until local multi-process source, actual tests, database readbacks, traces and measurable loads exist. No 100× throughput, production login/OIDC, high availability or guaranteed assignment win is claimed. Original 3 Nov 2026 14:00 deadline, <=3 README commands, 8 fixed mock tools, >=15 offline user-agent evaluations and six deliverables remain mandatory.

G4 live replay correction: despite strict=true, Groq returned HTTP 400 json_validate_failed because preferences.technician was omitted. Two application smoke failures are preserved. Prompt v3 includes a complete no-change output template; schema and independent validation remain mandatory, no automatic retries or fallback are introduced. This is a measured integration limitation, not a guarantee of model reliability.

The next live first turn correctly proposed noon for morning, but paraphrased evidence was rejected. Grounding now resolves only explicit source phrases 'a morning visit'/'mornings only' for a non-null morning proposal; the regression also rejects unsupported additions on unrelated turns. Final verification remains required.

The complete Chromium journey reached verified cancellation and mobile layout, then logout failed: the preserved handler_error is InsufficientPrivilege, because the intentionally restricted application role has SELECT/INSERT/UPDATE authority but no DELETE grant. Logout now expires the session in SQL, preserving its audit references while immediately denying authentication; the browser replay verifies the login screen.
