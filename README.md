# Orange Invest - local provider foundation (G0/G1)

Implemented: eight fixed mock provider tools, durable SQLite provider state,
seeded and forced faults, and direct contract tests. This is the provider layer;
chat, approval enforcement, workflow recovery, memory, browser UI and end-to-end
agent evals are **not implemented**. Do not use it as a completed booking agent.
No external providers, API services, credentials or payments are used.

Python 3.11+ is sufficient for the current runtime and tests. From this directory,
run these three commands (PowerShell or a normal terminal):

```text
python scripts/check_contract.py
python -m unittest discover -s tests -v
python -m app.provider_mock
```

The last command prints three synthetic plumber providers and available slots;
it creates `data/provider.sqlite3` once and never resets existing state. It does
not book anything or start a browser/server. Fixtures cover plumber, electrician
and ac servicing in Indiranagar/Koramangala for seven days after DB creation.
An older DB can correctly show no future slots. For a fresh isolated inspection,
choose a new path: `python -m app.provider_mock --db data/another-demo.sqlite3`.

To explicitly erase only the synthetic provider state and reseed its calendar,
run `python -m app.provider_mock reset-demo`. This is destructive to the demo
provider database; it is never called on startup. Use `--db <path>` to select an
isolated provider database.

`requirements.txt` pins optional pytest. In an environment with package access,
`python -m pip install -r requirements.txt` then `python -m pytest -q` is an
alternative test driver; pytest installation/execution was not verified here.
The standard-library test command above runs entirely offline. The final
three-command FastAPI interface will be added with G4; no nonexistent app.main
or browser demo is advertised now.

Tools are methods of `app.provider_mock.ProviderMock`. Construct with a file path
and trusted `user_id`; fixed tool signatures remain unchanged. Date ranges use
`{"start": "<aware ISO timestamp>", "end": "<aware ISO timestamp>"}` with an exclusive
end; slots are normalized to IST. See [decisions](DECISIONS.md) for precise fixture,
idempotency, timeout, identity and status interpretations. Constructor-only
`ScenarioConfig` is for controlled tests, never user chat. Provider methods do
not implement approvals; the later deterministic controller must guard writes.

To generate a new receipt with exact output, exit code, source hashes and source
snapshot, run `python scripts/run_checks.py --label my_g1_check` (a new label is
required). Existing red and green receipts are preserved under
`artifacts/receipts/`. They are provider evidence, not employer end-to-end traces
or scripted-user evals.

See [implementation plan](docs/implementation_plan.md) for all must-haves and
six deliverables, and [actual progress](docs/actual_progress.md) for gate status,
observed counts and evidence boundaries. The original PDF is preserved in
`source/FoundingEngineer-Assignment.pdf`; `CANONICAL.md` governs later work.
