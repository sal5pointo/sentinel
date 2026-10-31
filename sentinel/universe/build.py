"""Universe U0 builder — liquid ~500 / S&P-500-like with monthly PIT snapshots.

Offline/CI: uses vendored Nasdaq Trader fixtures + price/ADV fixture metrics.
Live (optional): same filters against downloaded Nasdaq Trader files + quote ADV.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sentinel.config import load_universe
from sentinel.data.symbols import (
    EXCLUDED_TYPES,
    ListedSymbol,
    load_default_fixtures,
    load_symbol_directory,
)
from sentinel.storage.db import Database


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    name: str
    exchange: str
    security_type: str
    price: float
    adv_usd: float
    listing_date: str | None


@dataclass(frozen=True)
class UniverseSnapshot:
    stage: str
    as_of_month: str  # YYYY-MM
    built_at: str
    source: str
    members: list[UniverseMember]

    @property
    def member_count(self) -> int:
        return len(self.members)


def _parse_listing_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def months_listed(listing: date | None, as_of: date) -> float | None:
    if listing is None:
        return None
    return (as_of.year - listing.year) * 12 + (as_of.month - listing.month)


def load_metrics_fixture(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Map symbol → {price, adv_usd, listing_date}."""
    if path is None:
        root = Path(__file__).resolve().parent.parent.parent
        for candidate in (
            root / "data" / "fixtures" / "universe" / "metrics.json",
            root / "tests" / "fixtures" / "universe" / "metrics.json",
        ):
            if candidate.is_file():
                path = candidate
                break
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("metrics fixture must be a JSON object")
    return {str(k).upper(): v for k, v in data.items()}


def filter_u0(
    listed: list[ListedSymbol],
    metrics: dict[str, dict[str, Any]],
    *,
    cfg: dict[str, Any] | None = None,
    as_of: date | None = None,
) -> list[UniverseMember]:
    """Apply U0 liquidity / listing / security-type filters."""
    cfg = cfg or load_universe()
    as_of = as_of or date.today()
    min_price = float(cfg.get("min_price", 5))
    min_adv = float(cfg.get("min_adv_usd", 25_000_000))
    min_months = float(cfg.get("min_listing_months", 6))
    exclude = set(cfg.get("exclude") or list(EXCLUDED_TYPES))
    size = int(cfg.get("size", 500))
    include_adrs = bool(cfg.get("include_large_adrs", True))

    members: list[UniverseMember] = []
    for row in listed:
        if row.test_issue:
            continue
        if row.security_type in exclude or row.etf:
            continue
        if row.security_type != "COMMON" and not (
            include_adrs and "ADR" in row.name.upper()
        ):
            continue
        m = metrics.get(row.symbol)
        if not m:
            continue
        price = float(m.get("price", 0))
        adv = float(m.get("adv_usd", 0))
        listing_raw = m.get("listing_date") or row.listing_date
        listing = _parse_listing_date(str(listing_raw) if listing_raw else None)
        listed_months = months_listed(listing, as_of)
        if price < min_price or adv < min_adv:
            continue
        if listed_months is not None and listed_months < min_months:
            continue
        # Missing listing date: allow if metrics present (fixture honesty).
        members.append(
            UniverseMember(
                symbol=row.symbol,
                name=row.name,
                exchange=row.exchange,
                security_type=row.security_type,
                price=price,
                adv_usd=adv,
                listing_date=listing.isoformat() if listing else None,
            )
        )

    # Prefer higher ADV when capping to stage size (S&P-500-like liquidity tilt).
    members.sort(key=lambda x: x.adv_usd, reverse=True)
    return members[:size]


def build_universe(
    *,
    symbol_paths: list[Path] | None = None,
    metrics_path: Path | None = None,
    as_of_month: str | None = None,
    source: str = "fixture",
    cfg: dict[str, Any] | None = None,
) -> UniverseSnapshot:
    cfg = cfg or load_universe()
    stage = str(cfg.get("stage", "U0"))
    today = date.today()
    month = as_of_month or f"{today.year:04d}-{today.month:02d}"
    as_of = date.fromisoformat(f"{month}-01")

    listed = (
        load_symbol_directory(symbol_paths) if symbol_paths else load_default_fixtures()
    )
    metrics = load_metrics_fixture(metrics_path)
    members = filter_u0(listed, metrics, cfg=cfg, as_of=as_of)
    return UniverseSnapshot(
        stage=stage,
        as_of_month=month,
        built_at=datetime.now(tz=UTC).isoformat(),
        source=source,
        members=members,
    )


def persist_snapshot(db: Database, snap: UniverseSnapshot) -> int:
    """Store point-in-time membership; replaces same stage+month if present."""
    existing = db.fetchall(
        "SELECT id FROM universe_snapshots WHERE stage = ? AND as_of_month = ?",
        (snap.stage, snap.as_of_month),
    )
    if existing:
        sid = int(existing[0]["id"])
        db.execute("DELETE FROM universe_members WHERE snapshot_id = ?", (sid,))
        db.execute(
            "UPDATE universe_snapshots SET built_at = ?, source = ?, member_count = ? WHERE id = ?",
            (snap.built_at, snap.source, snap.member_count, sid),
        )
    else:
        cur = db.execute(
            "INSERT INTO universe_snapshots(stage, as_of_month, built_at, source, member_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (snap.stage, snap.as_of_month, snap.built_at, snap.source, snap.member_count),
        )
        sid = int(cur.lastrowid)
    for m in snap.members:
        db.execute(
            "INSERT INTO universe_members("
            "snapshot_id, symbol, name, exchange, security_type, price, adv_usd, listing_date"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sid,
                m.symbol,
                m.name,
                m.exchange,
                m.security_type,
                m.price,
                m.adv_usd,
                m.listing_date,
            ),
        )
    return sid


def load_latest_members(db: Database, stage: str = "U0") -> list[str]:
    rows = db.fetchall(
        "SELECT m.symbol FROM universe_members m "
        "JOIN universe_snapshots s ON s.id = m.snapshot_id "
        "WHERE s.stage = ? ORDER BY s.as_of_month DESC, m.adv_usd DESC",
        (stage,),
    )
    # Deduplicate keeping first (latest month).
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        sym = str(r["symbol"])
        if sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


def snapshot_to_dict(snap: UniverseSnapshot) -> dict[str, Any]:
    return {
        "stage": snap.stage,
        "as_of_month": snap.as_of_month,
        "built_at": snap.built_at,
        "source": snap.source,
        "member_count": snap.member_count,
        "members": [asdict(m) for m in snap.members],
    }


# Back-compat for Phase 0 stub import sites.
def build_universe_stub() -> list[str]:
    snap = build_universe(source="fixture")
    return [m.symbol for m in snap.members]
