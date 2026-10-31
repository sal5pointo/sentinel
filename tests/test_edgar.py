"""EDGAR parsers — ≥5 real-shaped Form 4 / 8-K fixtures."""

from __future__ import annotations

from pathlib import Path

from sentinel.data.edgar import (
    load_companyfacts_fixtures,
    load_form4_fixtures,
    load_form8k_fixtures,
    parse_companyfacts,
    parse_form4_xml,
    parse_form8k_text,
    persist_form4,
    persist_form8k,
)
from sentinel.storage.db import Database

ROOT = Path(__file__).resolve().parent / "fixtures" / "edgar"


def test_form4_fixtures_at_least_five() -> None:
    filings = load_form4_fixtures(ROOT)
    assert len(filings) >= 5
    aapl = [f for f in filings if f.symbol == "AAPL"]
    assert len(aapl) >= 3
    for f in filings:
        assert f.accession
        assert f.cik
        assert f.transactions
        for tx in f.transactions:
            assert tx.shares > 0
            assert tx.transaction_code


def test_form4_parse_single() -> None:
    path = next((ROOT / "form4").glob("*000101*.xml"))
    filing = parse_form4_xml(path.read_text(encoding="utf-8"), accession="test-acc")
    assert filing.symbol == "AAPL"
    assert filing.transactions[0].is_acquisition
    assert filing.transactions[0].total_value_usd is not None


def test_form8k_fixtures_at_least_five() -> None:
    filings = load_form8k_fixtures(ROOT)
    assert len(filings) >= 5
    items_seen: set[str] = set()
    for f in filings:
        items_seen.update(f.items)
        assert f.accession
    assert "2.02" in items_seen or "1.01" in items_seen
    assert "2.06" in items_seen  # impairment fixture


def test_form8k_parse_items() -> None:
    text = "Item 2.02 Results of Operations\nItem 7.01 Regulation FD Disclosure"
    f = parse_form8k_text(text, accession="a", cik="320193", symbol="AAPL")
    assert "2.02" in f.items
    assert "7.01" in f.items


def test_companyfacts_fixtures() -> None:
    slices = load_companyfacts_fixtures(ROOT)
    assert len(slices) >= 5
    by = {s.symbol: s for s in slices}
    assert "AAPL" in by
    assert "Assets" in by["AAPL"].facts


def test_persist_filings(tmp_db: Path) -> None:
    db = Database(tmp_db)
    for f in load_form4_fixtures(ROOT)[:2]:
        persist_form4(db, f)
    for f in load_form8k_fixtures(ROOT)[:2]:
        persist_form8k(db, f)
    rows = db.fetchall("SELECT form FROM filings")
    assert len(rows) >= 4
    txs = db.fetchall("SELECT * FROM form4_transactions")
    assert len(txs) >= 1
    db.close()


def test_companyfacts_parse_dict() -> None:
    raw = {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "tickers": ["AAPL"],
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {"USD": [{"end": "2024-12-31", "val": 100, "form": "10-K"}]}
                }
            }
        },
    }
    s = parse_companyfacts(raw)
    assert s.symbol == "AAPL"
    assert s.facts["Assets"]["value"] == 100
