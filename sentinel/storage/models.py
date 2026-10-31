"""Lightweight row models / table DDL for Phase 0."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Initial schema version applied by migrations stub.
SCHEMA_VERSION = 1

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


@dataclass
class AuditEvent:
    ts: datetime
    category: str
    action: str
    detail: dict[str, Any]
    actor: str = "system"
