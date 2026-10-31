"""SEC EDGAR ingest — Form 4, key 8-K hooks, companyfacts for candidates.

Public EDGAR only. Declared User-Agent required for live fetches.
Offline/CI uses vendored fixtures under tests/fixtures/edgar.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_USER_AGENT = "SENTINEL/0.1 (personal research; contact: owner@localhost)"

# Slim 8-K item hooks we care about for catalyst flags.
KEY_8K_ITEMS = frozenset(
    {
        "1.01",  # Material definitive agreement
        "1.02",  # Termination of material agreement
        "2.01",  # Acquisition / disposition of assets
        "2.02",  # Results of operations
        "2.05",  # Exit costs / restructuring
        "2.06",  # Material impairment
        "5.02",  # Director/officer departure / appointment
        "7.01",  # Regulation FD
        "8.01",  # Other events
    }
)


@dataclass(frozen=True)
class Form4Transaction:
    accession: str
    cik: str
    symbol: str | None
    insider_name: str
    insider_role: str
    transaction_date: str | None
    transaction_code: str
    shares: float
    price_per_share: float | None
    total_value_usd: float | None
    is_acquisition: bool


@dataclass(frozen=True)
class Form4Filing:
    accession: str
    cik: str
    symbol: str | None
    filed_at: str
    issuer_name: str
    transactions: list[Form4Transaction]


@dataclass(frozen=True)
class Form8KFiling:
    accession: str
    cik: str
    symbol: str | None
    filed_at: str
    items: list[str]
    headline: str = ""
    raw_excerpt: str = ""


@dataclass(frozen=True)
class CompanyFactsSlice:
    cik: str
    symbol: str | None
    entity_name: str
    facts: dict[str, Any] = field(default_factory=dict)
    red_flags: list[str] = field(default_factory=list)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _element_text(node: ET.Element) -> str | None:
    """SEC ownership XML often wraps scalars in <value>…</value>."""
    if node.text and node.text.strip():
        return node.text.strip()
    for child in node:
        if _local(child.tag).lower() == "value" and child.text and child.text.strip():
            return child.text.strip()
    # Fallback: first non-empty descendant text
    for child in node.iter():
        if child is node:
            continue
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _find_text(node: ET.Element | None, *names: str) -> str | None:
    if node is None:
        return None
    want = {n.lower() for n in names}
    for child in node.iter():
        if _local(child.tag).lower() in want:
            text = _element_text(child)
            if text:
                return text
    return None


def _first_child(node: ET.Element, name: str) -> ET.Element | None:
    for child in node:
        if _local(child.tag).lower() == name.lower():
            return child
    return None


def parse_form4_xml(text: str, *, accession: str | None = None) -> Form4Filing:
    """Parse ownership XML (Form 4). Tolerant of namespaces."""
    root = ET.fromstring(text)
    accession = accession or _find_text(root, "accessionNumber") or "UNKNOWN"
    cik = _find_text(root, "cik", "issuerCik") or "0000000000"
    symbol = _find_text(root, "issuerTradingSymbol")
    issuer_name = _find_text(root, "issuerName") or ""
    filed_at = _find_text(root, "periodOfReport") or datetime.now(tz=UTC).date().isoformat()

    owner = None
    for child in root.iter():
        if _local(child.tag).lower() == "reportingowner":
            owner = child
            break
    insider_name = _find_text(owner, "rptOwnerName") or "UNKNOWN"
    role_bits: list[str] = []
    if owner is not None:
        rel = None
        for child in owner.iter():
            if _local(child.tag).lower() == "reportingownerrelationship":
                rel = child
                break
        if rel is not None:
            if (_find_text(rel, "isDirector") or "").lower() in {"1", "true"}:
                role_bits.append("Director")
            if (_find_text(rel, "isOfficer") or "").lower() in {"1", "true"}:
                title = _find_text(rel, "officerTitle") or "Officer"
                role_bits.append(title)
            if (_find_text(rel, "isTenPercentOwner") or "").lower() in {"1", "true"}:
                role_bits.append("10%")
    insider_role = ", ".join(role_bits) or "Insider"

    transactions: list[Form4Transaction] = []
    for node in root.iter():
        if _local(node.tag).lower() not in {"nonderivativetransaction", "derivativetransaction"}:
            continue
        code = _find_text(node, "transactionCode") or ""
        shares_s = _find_text(node, "transactionShares")
        price_s = _find_text(node, "transactionPricePerShare")
        date_s = _find_text(node, "transactionDate")
        acq = (_find_text(node, "transactionAcquiredDisposedCode") or "").upper()
        shares = float(shares_s) if shares_s else 0.0
        price = float(price_s) if price_s else None
        total = (shares * price) if price is not None else None
        is_acq = acq == "A" or code.upper() in {"P", "A"}
        transactions.append(
            Form4Transaction(
                accession=accession,
                cik=cik.zfill(10) if cik.isdigit() else cik,
                symbol=symbol.upper() if symbol else None,
                insider_name=insider_name,
                insider_role=insider_role,
                transaction_date=date_s,
                transaction_code=code.upper(),
                shares=shares,
                price_per_share=price,
                total_value_usd=total,
                is_acquisition=is_acq,
            )
        )

    return Form4Filing(
        accession=accession,
        cik=cik.zfill(10) if cik.isdigit() else cik,
        symbol=symbol.upper() if symbol else None,
        filed_at=filed_at,
        issuer_name=issuer_name,
        transactions=transactions,
    )


_ITEM_RE = re.compile(
    r"Item\s+(\d+\.\d+)\s*[:.\-]?\s*([^\n\r<]{0,120})",
    re.IGNORECASE,
)


def parse_form8k_text(
    text: str,
    *,
    accession: str,
    cik: str,
    symbol: str | None = None,
    filed_at: str | None = None,
) -> Form8KFiling:
    """Extract 8-K item numbers from HTML/text body."""
    found: list[str] = []
    headlines: list[str] = []
    for m in _ITEM_RE.finditer(text):
        item = m.group(1)
        if item not in found:
            found.append(item)
        title = m.group(2).strip(" .-:")
        if title:
            headlines.append(f"{item}: {title}")
    key = [i for i in found if i in KEY_8K_ITEMS]
    return Form8KFiling(
        accession=accession,
        cik=cik.zfill(10) if cik.isdigit() else cik,
        symbol=symbol.upper() if symbol else None,
        filed_at=filed_at or datetime.now(tz=UTC).date().isoformat(),
        items=key or found,
        headline="; ".join(headlines[:3]),
        raw_excerpt=text[:500],
    )


def parse_companyfacts(data: dict[str, Any] | str) -> CompanyFactsSlice:
    """Slim companyfacts path — surface a few XBRL facts for forensics."""
    payload = json.loads(data) if isinstance(data, str) else data
    cik = str(payload.get("cik") or payload.get("entity", {}).get("cik") or "0")
    entity = str(payload.get("entityName") or payload.get("entity", {}).get("name") or "")
    symbol = None
    tickers = payload.get("tickers") or payload.get("entity", {}).get("tickers") or []
    if isinstance(tickers, list) and tickers:
        symbol = str(tickers[0]).upper()
    facts_root = payload.get("facts") or {}
    us_gaap = facts_root.get("us-gaap") or facts_root.get("us_gaap") or {}
    slim: dict[str, Any] = {}
    for key in (
        "Assets",
        "Liabilities",
        "StockholdersEquity",
        "Revenues",
        "NetIncomeLoss",
        "CashAndCashEquivalentsAtCarryingValue",
        "Goodwill",
    ):
        block = us_gaap.get(key)
        if not isinstance(block, dict):
            continue
        units = block.get("units") or {}
        usd = units.get("USD") or []
        if usd:
            # Prefer most recent by end date
            sorted_pts = sorted(usd, key=lambda p: str(p.get("end") or ""), reverse=True)
            slim[key] = {
                "value": sorted_pts[0].get("val"),
                "end": sorted_pts[0].get("end"),
                "form": sorted_pts[0].get("form"),
            }
    return CompanyFactsSlice(
        cik=cik.zfill(10) if str(cik).isdigit() else str(cik),
        symbol=symbol,
        entity_name=entity,
        facts=slim,
    )


def load_form4_fixtures(directory: Path | None = None) -> list[Form4Filing]:
    root = _edgar_fixture_root(directory) / "form4"
    out: list[Form4Filing] = []
    for path in sorted(root.glob("*.xml")):
        accession = path.stem.replace("_", "-")
        out.append(parse_form4_xml(path.read_text(encoding="utf-8"), accession=accession))
    return out


def load_form8k_fixtures(directory: Path | None = None) -> list[Form8KFiling]:
    root = _edgar_fixture_root(directory) / "form8k"
    out: list[Form8KFiling] = []
    for path in sorted(root.glob("*.*")):
        meta_path = path.with_suffix(".json")
        meta: dict[str, Any] = {}
        if meta_path.is_file() and path.suffix.lower() != ".json":
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if path.suffix.lower() == ".json":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        out.append(
            parse_form8k_text(
                text,
                accession=str(meta.get("accession") or path.stem),
                cik=str(meta.get("cik") or "0000000000"),
                symbol=meta.get("symbol"),
                filed_at=meta.get("filed_at"),
            )
        )
    return out


def load_companyfacts_fixtures(directory: Path | None = None) -> list[CompanyFactsSlice]:
    root = _edgar_fixture_root(directory) / "companyfacts"
    out: list[CompanyFactsSlice] = []
    for path in sorted(root.glob("*.json")):
        out.append(parse_companyfacts(path.read_text(encoding="utf-8")))
    return out


def _edgar_fixture_root(directory: Path | None) -> Path:
    if directory is not None:
        return directory
    root = Path(__file__).resolve().parent.parent.parent
    for candidate in (root / "tests" / "fixtures" / "edgar", root / "data" / "fixtures" / "edgar"):
        if candidate.is_dir():
            return candidate
    return root / "tests" / "fixtures" / "edgar"


def persist_form4(db: Any, filing: Form4Filing) -> None:
    from sentinel.storage.db import Database

    assert isinstance(db, Database)
    now = datetime.now(tz=UTC).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO filings("
        "accession, form, cik, symbol, filed_at, accepted_at, items_json, raw_path, ingested_at"
        ") VALUES (?, '4', ?, ?, ?, NULL, ?, NULL, ?)",
        (
            filing.accession,
            filing.cik,
            filing.symbol,
            filing.filed_at,
            json.dumps({"issuer": filing.issuer_name, "n_tx": len(filing.transactions)}),
            now,
        ),
    )
    for tx in filing.transactions:
        db.execute(
            "INSERT OR IGNORE INTO form4_transactions("
            "accession, cik, symbol, insider_name, insider_role, transaction_date, "
            "transaction_code, shares, price_per_share, total_value_usd, is_acquisition"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tx.accession,
                tx.cik,
                tx.symbol,
                tx.insider_name,
                tx.insider_role,
                tx.transaction_date,
                tx.transaction_code,
                tx.shares,
                tx.price_per_share,
                tx.total_value_usd,
                1 if tx.is_acquisition else 0,
            ),
        )


def persist_form8k(db: Any, filing: Form8KFiling) -> None:
    from sentinel.storage.db import Database

    assert isinstance(db, Database)
    now = datetime.now(tz=UTC).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO filings("
        "accession, form, cik, symbol, filed_at, accepted_at, items_json, raw_path, ingested_at"
        ") VALUES (?, '8-K', ?, ?, ?, NULL, ?, NULL, ?)",
        (
            filing.accession,
            filing.cik,
            filing.symbol,
            filing.filed_at,
            json.dumps({"items": filing.items, "headline": filing.headline}),
            now,
        ),
    )


def form4_to_dict(filing: Form4Filing) -> dict[str, Any]:
    return {
        "accession": filing.accession,
        "cik": filing.cik,
        "symbol": filing.symbol,
        "filed_at": filing.filed_at,
        "issuer_name": filing.issuer_name,
        "transactions": [asdict(t) for t in filing.transactions],
    }


def ping_stub() -> str:
    return "edgar — Form 4 / 8-K / companyfacts parsers ready (fixture mode)"
