"""Sizing + settled-cash funding unit tests."""

from __future__ import annotations

import pytest
from sentinel.planner.funding import check_settled_cash
from sentinel.planner.sizing import size_shares


def test_size_shares_pilot_caps(config_dir: object) -> None:
    sized = size_shares(equity=100_000, entry=100.0, stop=96.0, bucket="A")
    assert sized.quantity >= 1
    assert sized.risk_pct <= 0.5  # pilot risk_pct
    assert sized.max_pos_pct <= 3
    assert sized.notional <= 100_000 * 0.03 + 1e-6


def test_settled_cash_ok(config_dir: object) -> None:
    chk = check_settled_cash(settled_cash=50_000, equity=100_000, notional=10_000)
    assert chk.ok
    assert chk.cash_after == pytest.approx(40_000)


def test_settled_cash_floor_breach(config_dir: object) -> None:
    # Floor 5% of 100k = 5k; spending 48k from 50k leaves 2k < floor
    chk = check_settled_cash(settled_cash=50_000, equity=100_000, notional=48_000)
    assert not chk.ok
    assert "breaches_cash_floor" in chk.reasons


def test_settled_cash_insufficient(config_dir: object) -> None:
    chk = check_settled_cash(settled_cash=5_000, equity=100_000, notional=10_000)
    assert not chk.ok
    assert "insufficient_settled_cash" in chk.reasons
    assert chk.proposed_sales
