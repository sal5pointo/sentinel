"""Goal math: required return to hit target equity (default $250k).

Honesty rule: if required CAGR ≳ 30%/yr, state plainly that risk rules will
NOT be loosened to hit a date.
"""

from __future__ import annotations

from dataclasses import dataclass

DECISION_FOOTER = "Decision support only — you approve every trade."


@dataclass(frozen=True)
class GoalMathRow:
    starting_equity: float
    target_equity: float
    years: float
    required_total_return_pct: float
    required_cagr_pct: float
    high_cagr_warning: bool


def required_cagr(starting: float, target: float, years: float) -> float:
    """Annualized CAGR as percent. Raises if inputs invalid."""
    if starting <= 0:
        raise ValueError("starting equity must be > 0")
    if target <= 0:
        raise ValueError("target equity must be > 0")
    if years <= 0:
        raise ValueError("years must be > 0")
    return ((target / starting) ** (1.0 / years) - 1.0) * 100.0


def compute_goal_math(
    starting_equity: float,
    *,
    target_equity: float = 250_000.0,
    horizons_years: list[float] | None = None,
    high_cagr_warning_pct: float = 30.0,
) -> list[GoalMathRow]:
    horizons = horizons_years or [2.0, 3.0]
    rows: list[GoalMathRow] = []
    for y in horizons:
        cagr = required_cagr(starting_equity, target_equity, y)
        total = (target_equity / starting_equity - 1.0) * 100.0
        rows.append(
            GoalMathRow(
                starting_equity=starting_equity,
                target_equity=target_equity,
                years=y,
                required_total_return_pct=total,
                required_cagr_pct=cagr,
                high_cagr_warning=cagr >= high_cagr_warning_pct,
            )
        )
    return rows


def render_goal_math_table(rows: list[GoalMathRow]) -> str:
    if not rows:
        return "(no rows)"
    start = rows[0].starting_equity
    target = rows[0].target_equity
    lines = [
        f"Goal math — grow ${start:,.0f} → ${target:,.0f}",
        "",
        f"{'Horizon':<10} {'Required CAGR':>14} {'Total return':>14} {'Warning':>10}",
        "-" * 52,
    ]
    any_warn = False
    for r in rows:
        warn = "YES" if r.high_cagr_warning else "no"
        any_warn = any_warn or r.high_cagr_warning
        lines.append(
            f"{r.years:>4.0f} years {r.required_cagr_pct:>13.1f}% "
            f"{r.required_total_return_pct:>13.1f}% {warn:>10}"
        )
    lines.append("")
    if any_warn:
        lines.append(
            "Required CAGR is ≳ 30%/yr for at least one horizon. "
            "Chasing that by raising risk per trade increases the chance of a large "
            "drawdown. SENTINEL risk rules will NOT be loosened to hit a calendar date. "
            "The goal is reached by compounding a positive edge, not by bet size."
        )
    else:
        lines.append(
            "Required CAGR is within a more plausible compounding band under current "
            "risk caps — still no guarantee; every trade needs your approval."
        )
    lines.append("")
    lines.append(DECISION_FOOTER)
    return "\n".join(lines)
