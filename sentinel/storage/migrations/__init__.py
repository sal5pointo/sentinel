"""Migration runner stub — Phase 0 applies v1 DDL only."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from sentinel.storage.models import DDL_V1, SCHEMA_VERSION


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
    if ver < 1:
        conn.executescript(DDL_V1)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(tz=UTC).isoformat()),
        )
        conn.commit()
        ver = SCHEMA_VERSION
    # Future: import numbered migration modules from this package.
    return ver
