"""Price / quote helpers + fixture OHLCV for offline scanners."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sentinel.broker.base import BrokerClient, Quote


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def fetch_quotes(client: BrokerClient, symbols: list[str]) -> list[Quote]:
    return client.get_quotes(symbols)


def fixture_ohlcv_path() -> Path | None:
    root = Path(__file__).resolve().parent.parent.parent
    for candidate in (
        root / "data" / "fixtures" / "prices" / "ohlcv.json",
        root / "tests" / "fixtures" / "prices" / "ohlcv.json",
    ):
        if candidate.is_file():
            return candidate
    return None


def load_ohlcv_fixture(
    symbols: list[str] | None = None,
    path: Path | None = None,
) -> dict[str, list[Bar]]:
    path = path or fixture_ohlcv_path()
    if path is None:
        return {}
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[Bar]] = {}
    for sym, bars in raw.items():
        if symbols is not None and sym.upper() not in {s.upper() for s in symbols}:
            continue
        out[sym.upper()] = [
            Bar(
                date=str(b["date"]),
                open=float(b["open"]),
                high=float(b["high"]),
                low=float(b["low"]),
                close=float(b["close"]),
                volume=float(b["volume"]),
            )
            for b in bars
        ]
    return out


def fifty_two_week_high(bars: list[Bar]) -> float:
    window = bars[-252:] if len(bars) >= 252 else bars
    return max(b.high for b in window)


def fifty_two_week_low(bars: list[Bar]) -> float:
    window = bars[-252:] if len(bars) >= 252 else bars
    return min(b.low for b in window)


def avg_volume(bars: list[Bar], lookback: int = 20) -> float:
    window = bars[-(lookback + 1) : -1] if len(bars) > lookback else bars[:-1]
    if not window:
        return 0.0
    return sum(b.volume for b in window) / len(window)
