"""Freshness monitor stubs."""

from __future__ import annotations

from pathlib import Path

from sentinel.ops.freshness import mark_edgar_fixture_ok, read_freshness, record_attempt
from sentinel.storage.db import Database


def test_freshness_defaults_and_edgar(tmp_db: Path) -> None:
    db = Database(tmp_db)
    rows = {r.source: r for r in read_freshness(db)}
    assert "schwab" in rows
    assert rows["schwab"].status == "unknown"
    mark_edgar_fixture_ok(db)
    rows2 = {r.source: r for r in read_freshness(db)}
    assert rows2["edgar"].status == "ok"
    record_attempt(db, "schwab", ok=False, detail="no oauth")
    rows3 = {r.source: r for r in read_freshness(db)}
    assert rows3["schwab"].status in {"unknown", "stale", "down"}
    db.close()
