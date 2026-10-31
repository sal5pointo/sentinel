"""Unit tests for $250k goal-math with sample equities."""

from __future__ import annotations

import pytest
from sentinel.reports.goal_math import (
    DECISION_FOOTER,
    compute_goal_math,
    render_goal_math_table,
    required_cagr,
)


def test_required_cagr_known_examples() -> None:
    # ~124%/yr for 50k → 250k in 2 years
    assert required_cagr(50_000, 250_000, 2) == pytest.approx(123.6, abs=0.5)
    # ~58%/yr for 100k → 250k in 2 years
    assert required_cagr(100_000, 250_000, 2) == pytest.approx(58.1, abs=0.5)
    # ~29%/yr for 150k → 250k in 2 years
    assert required_cagr(150_000, 250_000, 2) == pytest.approx(29.1, abs=0.5)
    # ~12%/yr for 200k → 250k in 2 years
    assert required_cagr(200_000, 250_000, 2) == pytest.approx(11.8, abs=0.5)


def test_compute_goal_math_warns_above_30() -> None:
    rows = compute_goal_math(50_000, target_equity=250_000, horizons_years=[2, 3])
    assert len(rows) == 2
    assert rows[0].high_cagr_warning is True
    assert rows[1].high_cagr_warning is True


def test_compute_goal_math_no_warn_near_target() -> None:
    rows = compute_goal_math(200_000, target_equity=250_000, horizons_years=[3])
    assert rows[0].high_cagr_warning is False


def test_render_includes_honesty_and_footer() -> None:
    text = render_goal_math_table(compute_goal_math(50_000))
    assert "will NOT be loosened" in text
    assert DECISION_FOOTER in text


def test_invalid_starting_equity() -> None:
    with pytest.raises(ValueError):
        required_cagr(0, 250_000, 2)
