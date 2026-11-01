# P1 release inclusion and preservation

Order ORANGE-CTO-20261101-P1-G2-001, manually dispatched by sponsor.

Include the original PDF/transcription, frozen canonical/AGENTS, ADRs, P0 archive,
CTO order, G1 application/provider fixtures/storage, provider tests, local check
scripts, README/requirements, historical red/green logs and exact source ZIPs,
synthetic provider evidence DB and JSON observations. Prior CODEX run notes are
historical records, not current authority. Historical progress remains dated;
new receipts establish subsequent outcomes without rewriting old claims.

Exclude caches, virtual environments, vendor dependencies, ignored data/ demo
DBs, temporary files, SQLite WAL/SHM, credentials/.env and private data. The only
included SQLite DB is the intentionally synthetic historical provider evidence.
No live service, personal dataset or credential is needed. .gitattributes disables
newline transformations to preserve source-contract and evidence hashes across
Git commit/checkout. This does not modify the verifier or any frozen input.

The release's full inclusion list and historical hashes are machine-recorded in
artifacts/receipts/p1_preflight_20261101.json. New post-commit G1 receipt is generated
by scripts/close_g1.py, which verifies source bytes against Git blobs and inspects
a fresh persisted timeout-after-success booking. No G2 source belongs in that
G1 implementation commit. No push is authorized.
