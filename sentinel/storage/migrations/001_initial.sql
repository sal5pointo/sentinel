-- Phase 0 initial schema (also embedded in models.DDL_V1 for apply_migrations).
-- Kept as a readable artifact for operators.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_hash TEXT NOT NULL,
    equity REAL,
    cash REAL,
    payload_json TEXT,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_hash TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL,
    average_price REAL,
    market_value REAL,
    payload_json TEXT,
    captured_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    refresh_expires_at TEXT,
    last_reminder_at TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    category TEXT NOT NULL,
    action TEXT NOT NULL,
    detail_json TEXT,
    actor TEXT NOT NULL DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS llm_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    request_json TEXT NOT NULL,
    response_json TEXT,
    schema_name TEXT,
    error TEXT
);
