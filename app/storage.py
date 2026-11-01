"""Provider-owned SQLite storage. No workflow/approval tables exist at G1."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_config (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1), config_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY, service TEXT NOT NULL, area TEXT NOT NULL,
    price INTEGER NOT NULL CHECK(price>=0), rating REAL NOT NULL,
    attributes_json TEXT NOT NULL, reviews_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_slots (
    provider_id TEXT NOT NULL REFERENCES providers(id), slot TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'available' CHECK(state IN ('available','taken')),
    PRIMARY KEY(provider_id, slot)
);
CREATE TABLE IF NOT EXISTS provider_holds (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, provider_id TEXT NOT NULL,
    slot TEXT NOT NULL, quoted_price INTEGER NOT NULL,
    expires_at TEXT NOT NULL, status TEXT NOT NULL
        CHECK(status IN ('held','expired','consumed','failed')),
    FOREIGN KEY(provider_id,slot) REFERENCES provider_slots(provider_id,slot)
);
CREATE TABLE IF NOT EXISTS provider_bookings (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, provider_id TEXT NOT NULL,
    service TEXT NOT NULL, slot TEXT NOT NULL, status TEXT NOT NULL
        CHECK(status IN ('booked','cancelled')),
    hold_id TEXT NOT NULL UNIQUE REFERENCES provider_holds(id),
    quoted_price INTEGER NOT NULL,
    FOREIGN KEY(provider_id,slot) REFERENCES provider_slots(provider_id,slot)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_provider_slot
    ON provider_bookings(provider_id,slot) WHERE status='booked';
CREATE TABLE IF NOT EXISTS provider_operation_outcomes (
    idempotency_key TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    action TEXT NOT NULL, payload_hash TEXT NOT NULL,
    response_json TEXT, error_code TEXT, attempts INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path):
        self.path = str(Path(path))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        db = self._open()
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)
        finally:
            db.close()

    def _open(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=5000')
        return db

    @contextmanager
    def connect(self, *, write=False):
        db = self._open()
        try:
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
