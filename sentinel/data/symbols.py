"""Nasdaq Trader symbol directory parser (free FTP/HTTP files).

Offline mode uses vendored fixtures under tests/fixtures/universe or
data/fixtures/universe. Live fetch prefers nasdaqtrader.com when allowed.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Security categories we exclude for U0 common-stock universe.
EXCLUDED_TYPES = frozenset(
    {
        "ETF",
        "ETN",
        "SPAC_PRE_DEAL",
        "PREFERRED",
        "WARRANT",
        "UNIT",
        "CEF",
    }
)

# Nasdaq Trader ETF indicator / test issue flags in otherlisted / nasdaqlisted.
_ETF_MARKERS = frozenset({"Y", "YES", "1", "TRUE"})


@dataclass(frozen=True)
class ListedSymbol:
    symbol: str
    name: str
    exchange: str
    security_type: str  # COMMON | ETF | PREFERRED | WARRANT | UNIT | OTHER
    etf: bool
    test_issue: bool
    listing_date: str | None = None  # YYYY-MM-DD when known


def _classify_row(
    *,
    symbol: str,
    name: str,
    etf_flag: str,
    category: str = "",
) -> str:
    sym = symbol.upper()
    n = name.upper()
    if etf_flag.strip().upper() in _ETF_MARKERS or " ETF" in f" {n}" or n.endswith(" ETF"):
        return "ETF"
    if "ETN" in n or "EXCHANGE TRADED NOTE" in n:
        return "ETN"
    if "WARRANT" in n or sym.endswith("W") and "WARRANT" in n:
        return "WARRANT"
    if " UNIT" in f" {n}" or n.endswith(" UNIT"):
        return "UNIT"
    if "PREFERRED" in n or " PFD" in n or category.upper() == "PREFERRED":
        return "PREFERRED"
    if "CLOSED-END" in n or "CLOSED END" in n or " CEF" in n:
        return "CEF"
    if "SPAC" in n and ("UNIT" in n or "RIGHT" in n):
        return "SPAC_PRE_DEAL"
    return "COMMON"


def parse_nasdaqlisted(text: str) -> list[ListedSymbol]:
    """Parse nasdaqlisted.txt (pipe-delimited Nasdaq Trader format)."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("File Creation")]
    if not lines:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|")
    out: list[ListedSymbol] = []
    for row in reader:
        symbol = (row.get("Symbol") or row.get("ACT Symbol") or "").strip().upper()
        if not symbol or symbol == "SYMBOL":
            continue
        name = (row.get("Security Name") or "").strip()
        etf_flag = (row.get("ETF") or "").strip()
        test = (row.get("Test Issue") or "N").strip().upper() in _ETF_MARKERS
        stype = _classify_row(symbol=symbol, name=name, etf_flag=etf_flag)
        out.append(
            ListedSymbol(
                symbol=symbol,
                name=name,
                exchange="NASDAQ",
                security_type=stype,
                etf=stype == "ETF",
                test_issue=test,
                listing_date=(row.get("Listing Date") or None) or None,
            )
        )
    return out


def parse_otherlisted(text: str) -> list[ListedSymbol]:
    """Parse otherlisted.txt (NYSE/AMEX etc.)."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("File Creation")]
    if not lines:
        return []
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|")
    out: list[ListedSymbol] = []
    for row in reader:
        symbol = (row.get("ACT Symbol") or row.get("Symbol") or "").strip().upper()
        if not symbol or symbol == "ACT SYMBOL":
            continue
        name = (row.get("Security Name") or "").strip()
        etf_flag = (row.get("ETF") or "").strip()
        exchange = (row.get("Exchange") or "NYSE").strip()
        test = (row.get("Test Issue") or "N").strip().upper() in _ETF_MARKERS
        stype = _classify_row(symbol=symbol, name=name, etf_flag=etf_flag)
        out.append(
            ListedSymbol(
                symbol=symbol,
                name=name,
                exchange=exchange,
                security_type=stype,
                etf=stype == "ETF",
                test_issue=test,
                listing_date=(row.get("Listing Date") or None) or None,
            )
        )
    return out


def load_symbol_directory(paths: Iterable[Path]) -> list[ListedSymbol]:
    """Load and merge nasdaqlisted / otherlisted style files."""
    by_sym: dict[str, ListedSymbol] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        name = path.name.lower()
        rows = parse_otherlisted(text) if "other" in name else parse_nasdaqlisted(text)
        for row in rows:
            by_sym[row.symbol] = row
    return list(by_sym.values())


def default_fixture_dir() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    for candidate in (
        root / "data" / "fixtures" / "universe",
        root / "tests" / "fixtures" / "universe",
    ):
        if candidate.is_dir():
            return candidate
    return root / "data" / "fixtures" / "universe"


def load_default_fixtures() -> list[ListedSymbol]:
    d = default_fixture_dir()
    paths = sorted(d.glob("*.txt"))
    if not paths:
        return []
    return load_symbol_directory(paths)
