"""Portfolio heat / position / restricted-list gates for paper plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sentinel.config import load_risk
from sentinel.risk.breakers import (
    BreakerAction,
    BreakerStatus,
    allows_new_entries,
    evaluate_breakers,
)


@dataclass(frozen=True)
class RiskVerdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    breaker: BreakerStatus | None = None
    half_size: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "half_size": self.half_size,
            "breaker": self.breaker.to_dict() if self.breaker else None,
        }


def check_plan_risk(
    *,
    symbol: str,
    bucket: str,
    notional: float,
    equity: float,
    open_positions: int,
    portfolio_heat_pct: float,
    day_start_equity: float,
    peak_equity: float,
    risk: dict[str, Any] | None = None,
) -> RiskVerdict:
    risk = risk or load_risk()
    reasons: list[str] = []

    restricted = {str(s).upper() for s in (risk.get("restricted_list") or [])}
    core = {str(s).upper() for s in (risk.get("core_holdings") or [])}
    if symbol.upper() in restricted:
        reasons.append("restricted_list")
    if symbol.upper() in core:
        reasons.append("core_holding_bucket_H_alerts_only")

    pilot = risk.get("pilot") or {}
    max_pos = int(pilot.get("max_positions") or risk.get("max_positions") or 8)
    if open_positions >= max_pos:
        reasons.append("max_positions")

    heat_max = float(risk.get("portfolio_heat_max_pct", 6))
    if portfolio_heat_pct > heat_max:
        reasons.append("portfolio_heat")

    allowed = {str(x).upper() for x in (pilot.get("buckets_allowed") or ["A", "D", "G"])}
    if bucket.upper() not in allowed:
        reasons.append("bucket_not_allowed")

    pos_pct = (notional / equity * 100.0) if equity > 0 else 999.0
    max_pos_pct = float(pilot.get("max_pos_pct") or 3)
    if pos_pct > max_pos_pct + 1e-9:
        reasons.append("max_pos_pct")

    breaker = evaluate_breakers(
        equity=equity,
        day_start_equity=day_start_equity,
        peak_equity=peak_equity,
        risk=risk,
    )
    half = breaker.action == BreakerAction.HALF_SIZE
    if not allows_new_entries(breaker):
        reasons.append(f"breaker_{breaker.action.value.lower()}")
    elif half:
        reasons.append("breaker_half_size")

    # HALF_SIZE is advisory (caller may cut qty); all other reasons block.
    hard = [r for r in reasons if r != "breaker_half_size"]
    return RiskVerdict(ok=len(hard) == 0, reasons=reasons, breaker=breaker, half_size=half)


def price_drift_pct(*, planned: float, live: float) -> float:
    if planned <= 0:
        return 999.0
    return abs(live - planned) / planned * 100.0


def drift_blocks_confirm(
    *,
    planned_price: float,
    live_price: float,
    max_drift_pct: float = 1.0,
) -> tuple[bool, float]:
    """Return (blocked, drift_pct)."""
    drift = price_drift_pct(planned=planned_price, live=live_price)
    return drift > max_drift_pct, round(drift, 4)
