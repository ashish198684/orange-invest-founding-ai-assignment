# G4 evidence map

Authority: CANONICAL P4, sponsor dispatched 2026-11-03. This map records ownership;
the generated receipts determine actual pass/fail. G5 is outside this dispatch.

| Requirement | Runtime | Executed proof |
| --- | --- | --- |
| Chat and retained corrections | `app/web/app.js`, `app/runtime/http_api.py`, existing controller | Chromium journey; E01–E03 |
| Exact immutable quote, revision and card-bound consent | Existing `WorkflowController`, issued-card API, rendered approval card | Chromium old-card removal; E06–E10, E15; unchanged G3X stale/forged/CSRF tests |
| One logical effect, truthful recovery | Existing PG outbox, fenced worker and independent provider RPC | E11–E19; real subprocess killed with exit 32 in E17; 39 G3X regressions |
| Cancellation/reschedule consent and readback | Existing change snapshots and fixed tools; appointment controls | E20–E22; extended browser test |
| User-approved memory, correction and forget | Existing `Memory`, browser controls | E23–E25, Chromium, G3X in-flight/cross-replica checks |
| Bounded model/tools/wall/retries | Existing isolated boundaries, per-run and durable budgets | E26–E27; unchanged G3X cap tests |
| Injection cannot change authority | Reviews rendered with `textContent`, excluded from intent parsing | E04–E05; Chromium real malicious review; fixed provider contract |
| Outcome grading and generated table | `scripts/g4_evals.py` HTTP ScriptedUser, separate read-only SQL role | 28 executed scenarios, per-case HTTP/SQL/JSONL, generated CSV/JSON |
| Reconnect and live trace | Same persisted workflow/operation IDs, authenticated activity projection | Chromium reload; API polling; source-linked per-run JSONL |

The eval HTTP server uses the production Handler on a private loopback port. A
test subclass fixes the interpreter clock and delays queue availability, allowing
controlled fresh worker processes. Neither override is a customer route or chat
field. PostgreSQL, consent validation, provider RPC/side effects and worker
execution are real. The original 65 SQLite tests and 39 G3X checks remain separate
from the 28 user-agent evaluations. Operational lease/TTL timers use real clocks;
the injected interpretation clock and fixture seed are retained in each receipt.

The first Chromium run exposed an actual dropped-click defect: provider buttons
appeared while the preceding request was finishing, and the busy guard silently
discarded a click. The queued-action fix and passing browser rerun are retained
beside the original failure screenshot and HTTP events. Early evaluation grader
errors and an interrupted stack rebuild are also retained; they are not hidden
or represented as successful application runs.

The separately enabled Groq adapter uses actual `openai/gpt-oss-20b` strict
structured output. Version 3 includes a complete nullable-output template;
changed fields are grounded in the latest request, with supported relative dates
resolved in IST. Twenty offline adapter tests cover
protocol failures, deadlines, semantic validation and concurrent memory changes.
The separate live and browser receipts identify actual model identity, returned
usage and measured latency. A configured key alone does not prove connectivity.
An earlier live browser failure exposed invented time constraints; its screenshot
and events are retained beside the grounding regression. The UTC/IST calendar
regression also retains its failing and passing test receipts.
