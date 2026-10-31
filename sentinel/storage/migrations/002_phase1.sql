-- Phase 1: universe PIT, filings, alerts, freshness

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
