"""Stop placement helpers — broker GTC child; never widen after entry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sentinel.config import load_risk


@dataclass(frozen=True)
class StopSpec:
    stop_price: float
    method: str
    atr: float | None = None
    never_widen: bool = True


def stop_from_atr(
    *,
    entry: float,
    atr: float,
    side: str = "BUY",
    bucket: str = "A",
    risk: dict[str, Any] | None = None,
) -> StopSpec:
    risk = risk or load_risk()
    b = (risk.get("buckets") or {}).get(bucket.upper()) or {}
    mult = float(b.get("stop_atr", 2.0))
    max_pct = float(b.get("stop_max_pct", 8))
    atr_dist = atr * mult
    pct_dist = entry * (max_pct / 100.0)
    dist = min(atr_dist, pct_dist) if atr > 0 else pct_dist
    stop = entry - dist if side.upper() == "BUY" else entry + dist
    return StopSpec(stop_price=round(stop, 4), method="atr_capped", atr=atr)


def stop_from_low52(
    *,
    entry: float,
    low_52w: float,
    atr: float = 0.0,
    risk: dict[str, Any] | None = None,
) -> StopSpec:
    """Bucket G style: low52 − 0.5·ATR (floor)."""
    _ = risk or load_risk()
    stop = low_52w - 0.5 * max(atr, 0.0)
    if stop >= entry:
        stop = entry * 0.95
    return StopSpec(stop_price=round(stop, 4), method="low52_minus_0.5atr", atr=atr)


def assert_never_widen(*, prior_stop: float, proposed_stop: float, side: str = "BUY") -> float:
    """Return the tighter stop; never move stop away from price (widen)."""
    if side.upper() == "BUY":
        return max(prior_stop, proposed_stop)  # higher stop = tighter for long
    return min(prior_stop, proposed_stop)
