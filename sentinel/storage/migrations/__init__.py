"""Migration runner — Phase 0 v1 + Phase 1 v2."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from sentinel.storage.models import DDL_V1, DDL_V2, SCHEMA_VERSION


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if not row:
        return 0
    ver = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations").fetchone()
    return int(ver["v"] if ver and ver["v"] is not None else 0)


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply pending migrations. Returns resulting schema version."""
    ver = current_version(conn)
    now = datetime.now(tz=UTC).isoformat()
    if ver < 1:
        conn.executescript(DDL_V1)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (1, now),
        )
        conn.commit()
        ver = 1
    if ver < 2:
        conn.executescript(DDL_V2)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (2, now),
        )
        conn.commit()
        ver = 2
    return ver if ver >= SCHEMA_VERSION else SCHEMA_VERSION
