"""52-week high/low scanner (MVP family 8.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sentinel.config import load_signals
from sentinel.data.prices import (
    Bar,
    avg_volume,
    fifty_two_week_high,
    fifty_two_week_low,
    load_ohlcv_fixture,
)


@dataclass(frozen=True)
class HighLowAlert:
    symbol: str
    direction: str  # near_high | near_low
    close: float
    high_52w: float
    low_52w: float
    pct_from_high: float
    pct_from_low: float
    volume_ratio: float
    score: float
    as_of: str
    family: str = "high_low"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def scan_high_low(
    ohlcv: dict[str, list[Bar]] | None = None,
    *,
    cfg: dict[str, Any] | None = None,
) -> list[HighLowAlert]:
    """Deterministic 52w hi/lo alerts. Alerts do not require confluence ≥2."""
    signals_cfg = cfg or load_signals()
    hl = signals_cfg.get("high_low") or {}
    near_high_pct = float(hl.get("near_high_pct", 5))
    volume_mult = float(hl.get("volume_mult", 1.5))
    # near_low uses same pct band
    near_low_pct = float(hl.get("near_low_pct", near_high_pct))

    data = ohlcv if ohlcv is not None else load_ohlcv_fixture()
    alerts: list[HighLowAlert] = []
    for symbol, bars in sorted(data.items()):
        if symbol == "SPY" or len(bars) < 30:
            continue
        last = bars[-1]
        hi = fifty_two_week_high(bars)
        lo = fifty_two_week_low(bars)
        if hi <= 0 or lo <= 0:
            continue
        pct_hi = (hi - last.close) / hi * 100.0
        pct_lo = (last.close - lo) / lo * 100.0 if lo else 999.0
        vol_avg = avg_volume(bars, 20)
        vol_ratio = (last.volume / vol_avg) if vol_avg else 0.0
        as_of = last.date

        if pct_hi <= near_high_pct and vol_ratio >= volume_mult:
            score = max(0.0, 100.0 - pct_hi * 10) * min(vol_ratio / volume_mult, 2.0) / 2.0
            alerts.append(
                HighLowAlert(
                    symbol=symbol,
                    direction="near_high",
                    close=last.close,
                    high_52w=hi,
                    low_52w=lo,
                    pct_from_high=round(pct_hi, 4),
                    pct_from_low=round(pct_lo, 4),
                    volume_ratio=round(vol_ratio, 4),
                    score=round(score, 2),
                    as_of=as_of,
                )
            )
        elif pct_lo <= near_low_pct and vol_ratio >= volume_mult * 0.8:
            score = max(0.0, 100.0 - pct_lo * 10) * min(vol_ratio / volume_mult, 2.0) / 2.0
            alerts.append(
                HighLowAlert(
                    symbol=symbol,
                    direction="near_low",
                    close=last.close,
                    high_52w=hi,
                    low_52w=lo,
                    pct_from_high=round(pct_hi, 4),
                    pct_from_low=round(pct_lo, 4),
                    volume_ratio=round(vol_ratio, 4),
                    score=round(score, 2),
                    as_of=as_of,
                )
            )
    alerts.sort(key=lambda a: a.score, reverse=True)
    return alerts


def run_scan_now() -> list[dict[str, Any]]:
    return [a.to_dict() for a in scan_high_low()]
