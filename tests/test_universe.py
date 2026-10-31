"""Universe U0 builder — offline fixtures."""

from __future__ import annotations

from pathlib import Path

from sentinel.storage.db import Database
from sentinel.universe.build import build_universe, load_latest_members, persist_snapshot

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "universe"


def test_u0_filters_exclude_etf_and_illiquid(config_dir: object) -> None:
    snap = build_universe(
        symbol_paths=[FIXTURES / "nasdaqlisted.txt", FIXTURES / "otherlisted.txt"],
        metrics_path=FIXTURES / "metrics.json",
        as_of_month="2025-10",
        source="fixture",
    )
    symbols = {m.symbol for m in snap.members}
    assert "AAPL" in symbols
    assert "NVDA" in symbols
    assert "JPM" in symbols
    # Exclusions
    assert "QQQ" not in symbols
    assert "SPY" not in symbols
    assert "TQQQ" not in symbols
    assert "ILLIQ" not in symbols  # ADV too low
    assert "PENNY" not in symbols  # price < $5
    assert "NEWCO" not in symbols  # listing age / unit
    assert snap.member_count >= 20
    assert snap.member_count <= 500


def test_u0_persist_pit(tmp_db: Path, config_dir: object) -> None:
    snap = build_universe(
        symbol_paths=[FIXTURES / "nasdaqlisted.txt", FIXTURES / "otherlisted.txt"],
        metrics_path=FIXTURES / "metrics.json",
        as_of_month="2025-10",
    )
    db = Database(tmp_db)
    sid = persist_snapshot(db, snap)
    assert sid > 0
    members = load_latest_members(db, "U0")
    assert "AAPL" in members
    # Rebuild same month replaces
    snap2 = build_universe(
        symbol_paths=[FIXTURES / "nasdaqlisted.txt", FIXTURES / "otherlisted.txt"],
        metrics_path=FIXTURES / "metrics.json",
        as_of_month="2025-10",
    )
    sid2 = persist_snapshot(db, snap2)
    assert sid2 == sid
    rows = db.fetchall("SELECT COUNT(*) AS c FROM universe_snapshots WHERE as_of_month='2025-10'")
    assert int(rows[0]["c"]) == 1
    db.close()
