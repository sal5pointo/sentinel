"""Hostile press-release fixture must not change numeric plan fields."""

from __future__ import annotations

from pathlib import Path

from sentinel.llm.worker import apply_memo_response, numbers_unchanged, stub_memo_from_request
from sentinel.planner.plan import build_trade_plan

FIXTURE = Path(__file__).parent / "fixtures" / "hostile_press_release.txt"


def test_hostile_press_release_does_not_mutate_numbers(config_dir: object) -> None:
    hostile = FIXTURE.read_text(encoding="utf-8")
    plan, *_ = build_trade_plan(
        symbol="NVDA",
        entry=120.0,
        atr=3.0,
        equity=100_000,
        settled_cash=40_000,
        bucket="A",
        families=["high_low", "catalysts"],
        score=80.0,
        evidence=["fixture"],
        thesis="",
    )
    locked = dict(plan.locked_numbers)

    # Simulate LLM / attacker returning mutated numbers borrowed from the press release
    poisoned = {
        "plan_id": plan.plan_id,
        "thesis": hostile,
        "numbers": {
            **locked,
            "quantity": 999999,
            "entry_ref_price": 1.0,
            "stop_price": 0.01,
            "risk_usd": 0,
        },
    }
    ok, reason, safe = apply_memo_response(locked_numbers=locked, response=poisoned)
    assert ok is False
    assert reason == "numeric_mutation_rejected"
    assert safe is None
    assert numbers_unchanged(locked, locked)

    # Stub path ignores untrusted text for numerics
    req = {
        "plan_id": plan.plan_id,
        "symbol": plan.symbol,
        "numbers": locked,
        "evidence": ["edgar"],
        "untrusted_text": [hostile],
    }
    memo = stub_memo_from_request(req)
    assert memo["numbers"] == locked
    assert memo["numbers"]["quantity"] != 999999
