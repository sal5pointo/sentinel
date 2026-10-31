"""Regime / macro gate — SPY vs 200DMA, breadth stub, event-risk stub."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sentinel.data.prices import Bar, load_ohlcv_fixture


@dataclass(frozen=True)
class RegimeState:
    risk_on: bool
    spy_close: float
    spy_ma200: float
    spy_vs_ma_pct: float
    breadth_pct_above_50dma: float | None
    event_risk: bool
    multiplier: float  # 0..1 gate applied to composite later
    as_of: str
    notes: list[str]
    family: str = "regime"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sma(bars: list[Bar], n: int) -> float | None:
    if len(bars) < n:
        return None
    window = bars[-n:]
    return sum(b.close for b in window) / n


def evaluate_regime(
    ohlcv: dict[str, list[Bar]] | None = None,
    *,
    event_risk: bool = False,
) -> RegimeState:
    data = ohlcv if ohlcv is not None else load_ohlcv_fixture()
    spy = data.get("SPY") or []
    notes: list[str] = []
    if len(spy) < 50:
        notes.append("insufficient_spy_history")
        return RegimeState(
            risk_on=False,
            spy_close=0.0,
            spy_ma200=0.0,
            spy_vs_ma_pct=0.0,
            breadth_pct_above_50dma=None,
            event_risk=event_risk,
            multiplier=0.5,
            as_of="",
            notes=notes,
        )

    ma200 = _sma(spy, min(200, len(spy))) or spy[-1].close
    close = spy[-1].close
    vs = (close - ma200) / ma200 * 100.0
    risk_on = close >= ma200 and not event_risk

    # Breadth on available non-SPY names vs 50DMA
    above = 0
    total = 0
    for sym, bars in data.items():
        if sym == "SPY" or len(bars) < 50:
            continue
        ma50 = _sma(bars, 50)
        if ma50 is None:
            continue
        total += 1
        if bars[-1].close >= ma50:
            above += 1
    breadth = (above / total * 100.0) if total else None
    if breadth is not None and breadth < 40:
        notes.append("weak_breadth")
        risk_on = risk_on and False

    mult = 1.0 if risk_on else 0.5
    if event_risk:
        mult = min(mult, 0.25)
        notes.append("event_risk_gate")
    if close < ma200:
        notes.append("spy_below_ma200")

    return RegimeState(
        risk_on=risk_on,
        spy_close=round(close, 4),
        spy_ma200=round(ma200, 4),
        spy_vs_ma_pct=round(vs, 4),
        breadth_pct_above_50dma=round(breadth, 2) if breadth is not None else None,
        event_risk=event_risk,
        multiplier=mult,
        as_of=spy[-1].date,
        notes=notes,
    )


def run_scan_now() -> dict[str, Any]:
    return evaluate_regime().to_dict()
