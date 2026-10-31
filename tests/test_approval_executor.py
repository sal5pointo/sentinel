"""Approval tokens, GET-never-executes, paper executor idempotency."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sentinel.approval.tokens import issue_token, validate_token
from sentinel.broker.base import Quote
from sentinel.broker.paper_broker import PaperBroker
from sentinel.execution.executor import Executor
from sentinel.ops import killswitch
from sentinel.planner.plan import build_trade_plan, persist_plan, update_plan_status
from sentinel.reports.dashboard.app import app
from sentinel.storage.db import Database


@pytest.fixture()
def insecure_webauthn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_INSECURE_WEBAUTHN_BYPASS", "1")


def _seed_plan(db: Database, *, entry: float = 200.0) -> str:
    plan, *_ = build_trade_plan(
        symbol="AAPL",
        entry=entry,
        atr=4.0,
        equity=100_000,
        settled_cash=50_000,
        bucket="A",
        families=["high_low", "insider"],
        score=70.0,
    )
    # Force pending even if funding edge cases
    if plan.quantity < 1:
        plan.quantity = 10
        plan.numbers["quantity"] = 10
        plan.status = "pending"
    persist_plan(db, plan)
    return plan.plan_id


def test_token_replay_rejected(tmp_db: object, config_dir: object) -> None:
    db = Database()
    try:
        plan_id = _seed_plan(db)
        issued = issue_token(db, plan_id)
        first = validate_token(db, issued.raw_token, consume=True)
        assert first.ok
        second = validate_token(db, issued.raw_token, consume=True)
        assert not second.ok
        assert second.reason == "replay"
    finally:
        db.close()


def test_get_confirm_never_executes(
    tmp_db: object, config_dir: object, insecure_webauthn: None
) -> None:
    killswitch.reset_for_tests()
    db = Database()
    try:
        plan_id = _seed_plan(db)
        tok = issue_token(db, plan_id).raw_token
    finally:
        db.close()

    client = TestClient(app)
    before = client.get(f"/api/plans/{plan_id}").json()
    resp = client.get(f"/p/{plan_id}", params={"t": tok})
    assert resp.status_code == 200
    assert "Approve plan" in resp.text
    assert "GET never executes" in resp.text
    after = client.get(f"/api/plans/{plan_id}").json()
    assert after["status"] == before["status"]
    assert after.get("broker_order_ids") in (None, [], before.get("broker_order_ids"))


def test_post_confirm_paper_execute(
    tmp_db: object, config_dir: object, insecure_webauthn: None
) -> None:
    killswitch.reset_for_tests()
    os.environ["TRADING_ENABLED"] = "false"
    db = Database()
    try:
        plan_id = _seed_plan(db, entry=200.0)
        tok = issue_token(db, plan_id).raw_token
    finally:
        db.close()

    broker = PaperBroker(starting_cash=100_000, slippage_bps=0)
    broker.seed_quote(Quote(symbol="AAPL", last=200.0, bid=199.5, ask=200.5))
    app.state.paper_broker = broker

    client = TestClient(app)
    resp = client.post(
        f"/p/{plan_id}/confirm",
        data={
            "t": tok,
            "decision": "approve",
            "challenge": "x",
            "credential_id": "x",
            "assertion": "bypass-token",
            "live_price": "200.0",
        },
    )
    assert resp.status_code == 200
    assert "Confirmed" in resp.text
    detail = client.get(f"/api/plans/{plan_id}").json()
    assert detail["status"] == "executed"
    positions = client.get("/api/positions").json()
    assert any(p["symbol"] == "AAPL" for p in positions["positions"])


def test_executor_idempotent(tmp_db: object, config_dir: object) -> None:
    killswitch.reset_for_tests()
    db = Database()
    broker = PaperBroker(starting_cash=100_000, slippage_bps=0)
    broker.seed_quote(Quote(symbol="AAPL", last=200.0, bid=199.5, ask=200.5))
    try:
        plan_id = _seed_plan(db)
        plan = __import__("sentinel.planner.plan", fromlist=["get_plan"]).get_plan(db, plan_id)
        assert plan is not None
        update_plan_status(db, plan, status="approved", decision="approve")
        ex = Executor(db, broker, max_drift_pct=5.0)
        r1 = ex.execute_approved_plan(plan_id, live_price=200.0)
        assert r1.ok
        r2 = ex.execute_approved_plan(plan_id, live_price=200.0)
        assert r2.ok
        assert r2.status in {"already_executed", "locked_or_done"}
        # Only one entry fill
        fills = db.fetchall("SELECT * FROM paper_fills WHERE plan_id = ?", (plan_id,))
        assert len(fills) == 1
    finally:
        db.close()


def test_halt_api_json(tmp_db: object, config_dir: object) -> None:
    killswitch.reset_for_tests()
    client = TestClient(app)
    resp = client.post("/api/halt/json", json={"action": "halt", "reason": "test"})
    assert resp.status_code == 200
    assert resp.json()["kill_state"] == "HALT"
    mode = client.get("/api/mode").json()
    assert mode["chip"] == "Halted"
    client.post("/api/halt/json", json={"action": "resume"})
    assert killswitch.get_state().value == "RUN"


def test_api_surface(tmp_db: object, config_dir: object) -> None:
    client = TestClient(app)
    assert client.get("/api/mode").status_code == 200
    assert client.get("/api/positions").status_code == 200
    assert client.get("/api/plans").status_code == 200
    assert client.get("/api/signals").status_code == 200
    assert client.get("/api/signals/freshness").status_code == 200
    health = client.get("/health").json()
    assert health["trading_enabled"] is False
    assert health["mode"] == "paper"
    assert health["phase"] == 2
