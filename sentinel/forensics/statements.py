"""Slim XBRL / companyfacts red-flag checks (quant forensics)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from sentinel.data.edgar import CompanyFactsSlice, load_companyfacts_fixtures


@dataclass(frozen=True)
class ForensicFlags:
    symbol: str
    cik: str
    flags: list[str]
    blocked: bool
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_companyfacts(slice_: CompanyFactsSlice) -> ForensicFlags:
    flags: list[str] = []
    facts = slice_.facts
    assets = (facts.get("Assets") or {}).get("value")
    equity = (facts.get("StockholdersEquity") or {}).get("value")
    goodwill = (facts.get("Goodwill") or {}).get("value")
    ni = (facts.get("NetIncomeLoss") or {}).get("value")
    cash = (facts.get("CashAndCashEquivalentsAtCarryingValue") or {}).get("value")
    liab = (facts.get("Liabilities") or {}).get("value")

    if assets and goodwill and assets > 0 and goodwill / assets > 0.35:
        flags.append("goodwill_heavy")
    if equity is not None and equity < 0:
        flags.append("negative_equity")
    if ni is not None and ni < 0 and cash is not None and assets and cash / assets < 0.03:
        flags.append("loss_making_thin_cash")
    if assets and liab and liab > assets * 0.95:
        flags.append("leverage_extreme")
    if assets and equity and abs((assets - liab) - equity) / max(assets, 1) > 0.15:
        # Soft accounting identity drift — informational
        flags.append("balance_sheet_identity_drift")

    # Hard block only on severe flags
    hard = {"negative_equity", "leverage_extreme"}
    blocked = bool(hard.intersection(flags))
    return ForensicFlags(
        symbol=slice_.symbol or "",
        cik=slice_.cik,
        flags=flags,
        blocked=blocked,
        detail={"facts": facts},
    )


def scan_forensics(
    slices: Iterable[CompanyFactsSlice] | None = None,
) -> list[ForensicFlags]:
    data = list(slices) if slices is not None else load_companyfacts_fixtures()
    return [evaluate_companyfacts(s) for s in data]
