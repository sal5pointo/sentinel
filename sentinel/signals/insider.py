"""Form 4 insider cluster scanner (MVP family 8.8)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from sentinel.config import load_signals
from sentinel.data.edgar import Form4Filing, Form4Transaction, load_form4_fixtures


@dataclass(frozen=True)
class InsiderClusterAlert:
    symbol: str
    direction: str  # cluster_buy | cluster_sell
    buyer_count: int
    total_buy_usd: float
    window_days: int
    accessions: list[str]
    score: float
    as_of: str
    family: str = "insider"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tx_date(tx: Form4Transaction) -> date | None:
    if not tx.transaction_date:
        return None
    try:
        return date.fromisoformat(tx.transaction_date[:10])
    except ValueError:
        return None


def scan_insider_clusters(
    filings: Iterable[Form4Filing] | None = None,
    *,
    cfg: dict[str, Any] | None = None,
    as_of: date | None = None,
) -> list[InsiderClusterAlert]:
    signals_cfg = cfg or load_signals()
    insider = signals_cfg.get("insider") or {}
    cluster_min = int(insider.get("cluster_min", 3))
    cluster_days = int(insider.get("cluster_days", 10))
    min_buy_usd = float(insider.get("min_buy_usd", 100_000))

    filings_list = list(filings) if filings is not None else load_form4_fixtures()
    as_of = as_of or date.today()
    start = as_of - timedelta(days=cluster_days)

    # Group acquisition buys by symbol
    by_symbol: dict[str, list[Form4Transaction]] = defaultdict(list)
    for filing in filings_list:
        for tx in filing.transactions:
            if not tx.symbol:
                continue
            d = _tx_date(tx)
            if d is None or d < start or d > as_of:
                continue
            code = (tx.transaction_code or "").upper()
            # Open-market-ish buys (P) or other acquisitions in the cluster window.
            if tx.is_acquisition and code in {"P", "A", "M"}:
                by_symbol[tx.symbol].append(tx)

    alerts: list[InsiderClusterAlert] = []
    for symbol, txs in sorted(by_symbol.items()):
        # Distinct insiders buying
        buyers = {t.insider_name for t in txs}
        buy_txs = [t for t in txs if (t.transaction_code or "").upper() == "P"]
        if not buy_txs:
            buy_txs = txs
        total = sum(t.total_value_usd or 0.0 for t in buy_txs)
        # Require enough distinct buyers (cluster); ignore tiny aggregate buys.
        if len(buyers) < cluster_min or total < min_buy_usd:
            continue
        accessions = sorted({t.accession for t in buy_txs})
        score = min(100.0, 20.0 * len(buyers) + total / 50_000.0)
        last_d = max(_tx_date(t) or as_of for t in buy_txs)
        alerts.append(
            InsiderClusterAlert(
                symbol=symbol,
                direction="cluster_buy",
                buyer_count=len(buyers),
                total_buy_usd=round(total, 2),
                window_days=cluster_days,
                accessions=accessions,
                score=round(score, 2),
                as_of=last_d.isoformat(),
            )
        )
    alerts.sort(key=lambda a: a.score, reverse=True)
    return alerts


def run_scan_now(*, as_of: str | None = None) -> list[dict[str, Any]]:
    d = date.fromisoformat(as_of) if as_of else date(2025, 10, 15)
    return [a.to_dict() for a in scan_insider_clusters(as_of=d)]
