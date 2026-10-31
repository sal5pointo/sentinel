"""MVP scanners — deterministic on fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sentinel.data.prices import load_ohlcv_fixture
from sentinel.forensics.scores import red_flag_gate
from sentinel.scoring.composite import compose_scores
from sentinel.signals import persist_alerts, run_all_scanners
from sentinel.signals.catalysts import scan_catalysts
from sentinel.signals.high_low import scan_high_low
from sentinel.signals.insider import scan_insider_clusters
from sentinel.signals.regime import evaluate_regime
from sentinel.storage.db import Database

PRICES = Path(__file__).resolve().parent / "fixtures" / "prices" / "ohlcv.json"


def test_high_low_deterministic(config_dir: object) -> None:
    ohlcv = load_ohlcv_fixture(path=PRICES)
    a1 = scan_high_low(ohlcv)
    a2 = scan_high_low(ohlcv)
    assert [x.to_dict() for x in a1] == [x.to_dict() for x in a2]
    dirs = {a.direction for a in a1}
    symbols = {a.symbol for a in a1}
    assert "near_high" in dirs or "near_low" in dirs
    assert symbols & {"NVDA", "META", "INTC"}


def test_insider_cluster_aapl(config_dir: object) -> None:
    alerts = scan_insider_clusters(as_of=date(2025, 10, 15))
    by = {a.symbol: a for a in alerts}
    assert "AAPL" in by
    assert by["AAPL"].buyer_count >= 3
    assert by["AAPL"].direction == "cluster_buy"


def test_catalysts_flags(config_dir: object) -> None:
    alerts = scan_catalysts()
    assert len(alerts) >= 5
    tags = {t for a in alerts for t in a.tags}
    assert tags & {"earnings_results", "impairment", "material_agreement", "buyback"}


def test_regime_spy(config_dir: object) -> None:
    ohlcv = load_ohlcv_fixture(path=PRICES)
    state = evaluate_regime(ohlcv)
    assert state.spy_close > 0
    assert state.spy_ma200 > 0
    assert 0 < state.multiplier <= 1


def test_forensics_gate(config_dir: object) -> None:
    gate = red_flag_gate()
    assert "passed" in gate and "blocked" in gate
    # INTC fixture is loss-making with goodwill — may warn but not necessarily block
    assert isinstance(gate["warnings"], dict)


def test_composite_confluence_stub(config_dir: object) -> None:
    bundle = run_all_scanners()
    scores = compose_scores(
        high_low=bundle["high_low"],
        insider=bundle["insider"],
        catalysts=bundle["catalysts"],
        forensics=bundle["forensics"],
        regime_multiplier=bundle["regime"]["multiplier"],
    )
    assert scores
    # Alerts exist without requiring confluence; stub still computes flag
    assert any(hasattr(s, "confluence_ok") for s in scores)


def test_persist_alerts(tmp_db: Path, config_dir: object) -> None:
    bundle = run_all_scanners()
    db = Database(tmp_db)
    n = persist_alerts(db, bundle)
    assert n >= 1
    rows = db.fetchall("SELECT family FROM signal_alerts")
    assert len(rows) == n
    db.close()
