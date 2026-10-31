"""Slim catalyst flags from 8-K items + optional earnings-date hooks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from sentinel.data.edgar import KEY_8K_ITEMS, Form8KFiling, load_form8k_fixtures

# Map 8-K items → catalyst tags
ITEM_TAGS: dict[str, str] = {
    "1.01": "material_agreement",
    "1.02": "agreement_termination",
    "2.01": "acquisition",
    "2.02": "earnings_results",
    "2.05": "restructuring",
    "2.06": "impairment",
    "5.02": "officer_change",
    "7.01": "reg_fd",
    "8.01": "other_event",
}


@dataclass(frozen=True)
class CatalystAlert:
    symbol: str
    direction: str  # flag polarity: positive | negative | neutral
    tags: list[str]
    items: list[str]
    accession: str
    score: float
    as_of: str
    headline: str
    family: str = "catalysts"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _polarity(items: list[str]) -> str:
    neg = {"2.05", "2.06", "1.02"}
    pos = {"1.01", "2.01", "2.02", "8.01"}
    if any(i in neg for i in items):
        return "negative"
    if any(i in pos for i in items):
        return "positive"
    return "neutral"


def scan_catalysts(
    filings: Iterable[Form8KFiling] | None = None,
) -> list[CatalystAlert]:
    filings_list = list(filings) if filings is not None else load_form8k_fixtures()
    alerts: list[CatalystAlert] = []
    for f in filings_list:
        if not f.symbol:
            continue
        key_items = [i for i in f.items if i in KEY_8K_ITEMS]
        if not key_items:
            continue
        tags = [ITEM_TAGS.get(i, i) for i in key_items]
        # Buyback heuristic in headline or body excerpt
        hl = f"{f.headline} {f.raw_excerpt}".lower()
        if "repurchase" in hl or "buyback" in hl:
            tags.append("buyback")
        direction = _polarity(key_items)
        score = 40.0 + 10.0 * len(key_items)
        if "buyback" in tags:
            score += 15.0
        if direction == "negative":
            score = min(score, 55.0)
        alerts.append(
            CatalystAlert(
                symbol=f.symbol,
                direction=direction,
                tags=sorted(set(tags)),
                items=key_items,
                accession=f.accession,
                score=round(min(score, 100.0), 2),
                as_of=f.filed_at,
                headline=f.headline[:200],
            )
        )
    alerts.sort(key=lambda a: a.score, reverse=True)
    return alerts


def run_scan_now() -> list[dict[str, Any]]:
    return [a.to_dict() for a in scan_catalysts()]
