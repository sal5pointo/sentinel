"""Daily / EOD report stubs — Phase 0 wires goal math only."""

from __future__ import annotations

from sentinel.reports.goal_math import compute_goal_math, render_goal_math_table


def build_phase0_goal_report(starting_equity: float, target_equity: float = 250_000.0) -> str:
    rows = compute_goal_math(starting_equity, target_equity=target_equity)
    return render_goal_math_table(rows)
