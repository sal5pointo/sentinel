"""Lightweight row models / table DDL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Schema versions applied by migrations.
SCHEMA_VERSION = 3

DDL_V1 = """
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
"""

DDL_V2 = """
CREATE TABLE IF NOT EXISTS universe_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    as_of_month TEXT NOT NULL,
    built_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'fixture',
    member_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(stage, as_of_month)
);

CREATE TABLE IF NOT EXISTS universe_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES universe_snapshots(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    name TEXT,
    exchange TEXT,
    security_type TEXT,
    price REAL,
    adv_usd REAL,
    listing_date TEXT,
    UNIQUE(snapshot_id, symbol)
);

CREATE TABLE IF NOT EXISTS filings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accession TEXT NOT NULL UNIQUE,
    form TEXT NOT NULL,
    cik TEXT NOT NULL,
    symbol TEXT,
    filed_at TEXT NOT NULL,
    accepted_at TEXT,
    items_json TEXT,
    raw_path TEXT,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS form4_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accession TEXT NOT NULL,
    cik TEXT NOT NULL,
    symbol TEXT,
    insider_name TEXT,
    insider_role TEXT,
    transaction_date TEXT,
    transaction_code TEXT,
    shares REAL,
    price_per_share REAL,
    total_value_usd REAL,
    is_acquisition INTEGER NOT NULL DEFAULT 0,
    UNIQUE(accession, insider_name, transaction_date, transaction_code, shares)
);

CREATE TABLE IF NOT EXISTS signal_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    family TEXT NOT NULL,
    direction TEXT,
    score REAL,
    detail_json TEXT,
    as_of TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_freshness (
    source TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_success_at TEXT,
    last_attempt_at TEXT,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS kill_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state TEXT NOT NULL DEFAULT 'RUN',
    reason TEXT,
    updated_at TEXT NOT NULL
);
"""

DDL_V3 = """
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
"""


@dataclass
class AuditEvent:
    ts: datetime
    category: str
    action: str
    detail: dict[str, Any]
    actor: str = "system"
