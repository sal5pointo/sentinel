"""Circuit breakers — daily loss / drawdown gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from sentinel.config import load_risk
from sentinel.ops import killswitch


class BreakerAction(StrEnum):
    CLEAR = "CLEAR"
    HALF_SIZE = "HALF_SIZE"
    REDUCE_ONLY = "REDUCE_ONLY"
    HALT = "HALT"


@dataclass(frozen=True)
class BreakerStatus:
    action: BreakerAction
    daily_loss_pct: float
    drawdown_pct: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["action"] = self.action.value
        return d


def evaluate_breakers(
    *,
    equity: float,
    day_start_equity: float,
    peak_equity: float,
    risk: dict[str, Any] | None = None,
    respect_killswitch: bool = True,
) -> BreakerStatus:
    risk = risk or load_risk()
    cfg = risk.get("breakers") or {}
    daily_lim = float(cfg.get("daily_loss_pct", 3))
    dd_half = float(cfg.get("dd_half_size_pct", 7))
    dd_reduce = float(cfg.get("dd_reduce_only_pct", 12))
    dd_halt = float(cfg.get("dd_halt_pct", 20))

    if day_start_equity <= 0 or peak_equity <= 0:
        return BreakerStatus(BreakerAction.HALT, 0.0, 0.0, ["invalid_equity_baseline"])

    daily_loss_pct = max(0.0, (day_start_equity - equity) / day_start_equity * 100.0)
    drawdown_pct = max(0.0, (peak_equity - equity) / peak_equity * 100.0)
    reasons: list[str] = []
    action = BreakerAction.CLEAR

    if respect_killswitch and killswitch.get_state() == killswitch.KillState.HALT:
        return BreakerStatus(
            BreakerAction.HALT,
            round(daily_loss_pct, 4),
            round(drawdown_pct, 4),
            ["killswitch_halt"],
        )

    if daily_loss_pct >= daily_lim or drawdown_pct >= dd_halt:
        action = BreakerAction.HALT
        if daily_loss_pct >= daily_lim:
            reasons.append("daily_loss")
        if drawdown_pct >= dd_halt:
            reasons.append("dd_halt")
    elif drawdown_pct >= dd_reduce:
        action = BreakerAction.REDUCE_ONLY
        reasons.append("dd_reduce_only")
    elif drawdown_pct >= dd_half:
        action = BreakerAction.HALF_SIZE
        reasons.append("dd_half_size")

    return BreakerStatus(
        action,
        round(daily_loss_pct, 4),
        round(drawdown_pct, 4),
        reasons,
    )


def allows_new_entries(status: BreakerStatus) -> bool:
    return status.action in {BreakerAction.CLEAR, BreakerAction.HALF_SIZE}
