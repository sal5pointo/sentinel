"""Position sizing from risk.yaml buckets (deterministic; no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sentinel.config import load_risk


@dataclass(frozen=True)
class SizeResult:
    quantity: float
    risk_usd: float
    risk_pct: float
    max_pos_pct: float
    entry: float
    stop: float
    notional: float
    capped_by: str | None = None


def _bucket_cfg(risk: dict[str, Any], bucket: str) -> dict[str, Any]:
    buckets = risk.get("buckets") or {}
    cfg = buckets.get(bucket.upper())
    if not cfg:
        raise ValueError(f"Unknown risk bucket: {bucket}")
    if cfg.get("enabled") is False:
        raise ValueError(f"Bucket {bucket} is disabled")
    return cfg


def size_shares(
    *,
    equity: float,
    entry: float,
    stop: float,
    bucket: str = "A",
    risk: dict[str, Any] | None = None,
    use_pilot_caps: bool = True,
) -> SizeResult:
    """Risk-based share count: risk_usd / |entry - stop|, capped by max_pos_pct."""
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be positive")
    if equity <= 0:
        raise ValueError("equity must be positive")
    risk = risk or load_risk()
    b = _bucket_cfg(risk, bucket)
    risk_pct = float(b.get("risk_pct", 1.0))
    max_pos_pct = float(b.get("max_pos_pct", 15))

    if use_pilot_caps:
        pilot = risk.get("pilot") or {}
        allowed = {str(x).upper() for x in (pilot.get("buckets_allowed") or ["A", "D", "G"])}
        if bucket.upper() not in allowed:
            raise ValueError(f"Bucket {bucket} not in pilot.buckets_allowed")
        risk_pct = min(risk_pct, float(pilot.get("risk_pct", risk_pct)))
        max_pos_pct = min(max_pos_pct, float(pilot.get("max_pos_pct", max_pos_pct)))

    per_share_risk = abs(entry - stop)
    if per_share_risk <= 0:
        raise ValueError("stop must differ from entry")

    risk_usd = equity * (risk_pct / 100.0)
    qty_risk = risk_usd / per_share_risk
    max_notional = equity * (max_pos_pct / 100.0)
    qty_pos = max_notional / entry
    quantity = float(int(min(qty_risk, qty_pos)))  # whole shares
    capped_by = None
    if qty_pos < qty_risk:
        capped_by = "max_pos_pct"
    elif quantity < qty_risk:
        capped_by = "whole_share"
    if quantity < 1:
        quantity = 0.0
        capped_by = "below_one_share"
    notional = quantity * entry
    return SizeResult(
        quantity=quantity,
        risk_usd=round(risk_usd, 2),
        risk_pct=risk_pct,
        max_pos_pct=max_pos_pct,
        entry=entry,
        stop=stop,
        notional=round(notional, 2),
        capped_by=capped_by,
    )
