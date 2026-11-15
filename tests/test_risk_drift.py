"""Price-drift guard + breaker unit tests."""

from __future__ import annotations

import pytest
from sentinel.ops import killswitch
from sentinel.risk.breakers import BreakerAction, evaluate_breakers
from sentinel.risk.rules import drift_blocks_confirm


def test_drift_blocks_when_over_threshold() -> None:
    blocked, drift = drift_blocks_confirm(
        planned_price=100.0, live_price=102.0, max_drift_pct=1.0
    )
    assert blocked is True
    assert drift == pytest.approx(2.0)


def test_drift_allows_within_threshold() -> None:
    blocked, drift = drift_blocks_confirm(
        planned_price=100.0, live_price=100.5, max_drift_pct=1.0
    )
    assert blocked is False
    assert drift == pytest.approx(0.5)


def test_breakers_halt_on_daily_loss(config_dir: object) -> None:
    killswitch.reset_for_tests()
    status = evaluate_breakers(
        equity=96_000, day_start_equity=100_000, peak_equity=100_000
    )
    assert status.action == BreakerAction.HALT
    assert "daily_loss" in status.reasons


def test_breakers_respect_killswitch(config_dir: object) -> None:
    killswitch.reset_for_tests()
    killswitch.halt("test")
    status = evaluate_breakers(
        equity=100_000, day_start_equity=100_000, peak_equity=100_000
    )
    assert status.action == BreakerAction.HALT
    killswitch.reset_for_tests()
