"""Settled-cash / good-faith funding stubs for cash accounts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sentinel.config import load_risk


@dataclass(frozen=True)
class FundingCheck:
    ok: bool
    settled_cash: float
    required_notional: float
    cash_floor_usd: float
    cash_after: float
    shortfall: float = 0.0
    reasons: list[str] = field(default_factory=list)
    proposed_sales: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_settled_cash(
    *,
    settled_cash: float,
    equity: float,
    notional: float,
    risk: dict[str, Any] | None = None,
    use_margin_borrowing: bool | None = None,
) -> FundingCheck:
    """Ensure purchase leaves cash_floor_pct and does not exceed settled cash (no GFV)."""
    risk = risk or load_risk()
    floor_pct = float(risk.get("cash_floor_pct", 5))
    margin = (
        bool(risk.get("use_margin_borrowing", False))
        if use_margin_borrowing is None
        else use_margin_borrowing
    )
    floor_usd = equity * (floor_pct / 100.0)
    reasons: list[str] = []
    if margin:
        # Explicitly out of MVP default — still refuse borrowing unless owner flips YAML.
        reasons.append("margin_borrowing_requested_but_mvp_cash_only")

    cash_after = settled_cash - notional
    shortfall = 0.0
    ok = True
    if notional > settled_cash + 1e-9:
        ok = False
        shortfall = notional - settled_cash
        reasons.append("insufficient_settled_cash")
    if cash_after < floor_usd - 1e-9:
        ok = False
        shortfall = max(shortfall, floor_usd - cash_after)
        reasons.append("breaches_cash_floor")
    if margin:
        ok = False

    proposed: list[dict[str, Any]] = []
    if shortfall > 0:
        proposed.append(
            {
                "action": "sell_to_fund",
                "approx_usd": round(shortfall, 2),
                "note": "Stub — owner picks symbols; never auto-sell without approval.",
            }
        )

    return FundingCheck(
        ok=ok,
        settled_cash=settled_cash,
        required_notional=notional,
        cash_floor_usd=round(floor_usd, 2),
        cash_after=round(cash_after, 2),
        shortfall=round(shortfall, 2),
        reasons=reasons,
        proposed_sales=proposed,
    )
