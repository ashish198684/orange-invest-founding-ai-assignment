# Architecture decisions — Orange Invest

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
