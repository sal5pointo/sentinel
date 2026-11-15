"""TradePlan persistence + schema v3."""

from __future__ import annotations

from sentinel.planner.plan import build_trade_plan, get_plan, list_plans, persist_plan
from sentinel.storage.db import Database
from sentinel.storage.models import SCHEMA_VERSION


def test_schema_v3(tmp_db: object, config_dir: object) -> None:
    db = Database()
    try:
        rows = db.fetchall("SELECT MAX(version) AS v FROM schema_migrations")
        assert int(rows[0]["v"]) == SCHEMA_VERSION == 3
        tables = {
            r["name"]
            for r in db.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "trade_plans" in tables
        assert "approval_tokens" in tables
        assert "paper_orders" in tables
    finally:
        db.close()


def test_persist_and_load_plan(tmp_db: object, config_dir: object) -> None:
    plan, verdict, funding, *_ = build_trade_plan(
        symbol="MSFT",
        entry=400.0,
        atr=5.0,
        equity=100_000,
        settled_cash=40_000,
        bucket="D",
        families=["insider", "catalysts"],
        score=66.0,
    )
    db = Database()
    try:
        persist_plan(db, plan)
        loaded = get_plan(db, plan.plan_id)
        assert loaded is not None
        assert loaded.symbol == "MSFT"
        assert loaded.numbers["stop_price"] == plan.stop_price
        assert loaded.locked_numbers["quantity"] == plan.quantity
        listed = list_plans(db)
        assert any(p.plan_id == plan.plan_id for p in listed)
        assert isinstance(verdict.ok, bool)
        assert isinstance(funding.ok, bool)
    finally:
        db.close()
