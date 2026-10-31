-- Phase 2: trade plans, approvals, paper orders / fills

CREATE TABLE IF NOT EXISTS trade_plans (
    plan_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    bucket TEXT NOT NULL,
    quantity REAL NOT NULL,
    entry_ref_price REAL NOT NULL,
    entry_limit REAL,
    stop_price REAL NOT NULL,
    risk_usd REAL NOT NULL,
    risk_pct REAL NOT NULL,
    max_pos_pct REAL,
    families_json TEXT NOT NULL,
    score REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    funding_json TEXT,
    numbers_json TEXT NOT NULL,
    thesis TEXT,
    evidence_json TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    decided_at TEXT,
    decision TEXT,
    decision_reason TEXT,
    executed_at TEXT,
    broker_order_ids_json TEXT
);

CREATE TABLE IF NOT EXISTS approval_tokens (
    token_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES trade_plans(plan_id),
    token_hash TEXT NOT NULL UNIQUE,
    action_hint TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    single_use INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS paper_orders (
    order_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    role TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    order_type TEXT NOT NULL,
    limit_price REAL,
    stop_price REAL,
    status TEXT NOT NULL,
    fill_price REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS paper_fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    fill_price REAL NOT NULL,
    filled_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_locks (
    plan_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    detail_json TEXT
);
