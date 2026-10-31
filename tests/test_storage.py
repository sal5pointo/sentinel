"""SQLite WAL + migrations stub."""

from __future__ import annotations

from pathlib import Path

from sentinel.ops.audit import AuditLog
from sentinel.storage.db import Database
from sentinel.storage.migrations import current_version


def test_migrations_apply(tmp_db: Path) -> None:
    db = Database(tmp_db)
    assert current_version(db.conn) == 3
    mode = db.conn.execute("PRAGMA journal_mode;").fetchone()[0]
    assert str(mode).lower() == "wal"
    tables = {
        r[0]
        for r in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "universe_snapshots" in tables
    assert "signal_alerts" in tables
    assert "source_freshness" in tables
    assert "trade_plans" in tables
    db.close()


def test_audit_log_jsonl_and_db(tmp_db: Path, tmp_path: Path) -> None:
    db = Database(tmp_db)
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(db=db, jsonl_path=path)
    audit.record("test", "ping", {"ok": True}, actor="pytest")
    rows = db.fetchall("SELECT category, action FROM audit_events")
    assert len(rows) == 1
    assert rows[0]["action"] == "ping"
    assert path.exists()
    assert "ping" in path.read_text(encoding="utf-8")
    db.close()
