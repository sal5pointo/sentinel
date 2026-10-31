"""Source freshness monitor — Schwab + EDGAR (stubs OK if Schwab offline)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sentinel.storage.db import Database

STALE_AFTER = {
    "schwab": timedelta(hours=2),
    "edgar": timedelta(hours=12),
}


@dataclass(frozen=True)
class FreshnessRow:
    source: str
    status: str  # ok | stale | down | unknown
    last_success_at: str | None
    last_attempt_at: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _classify(source: str, last_success: str | None, now: datetime) -> str:
    if not last_success:
        return "unknown" if source == "schwab" else "down"
    try:
        ts = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
    except ValueError:
        return "down"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age = now - ts
    limit = STALE_AFTER.get(source, timedelta(hours=6))
    if age <= limit:
        return "ok"
    if age <= limit * 3:
        return "stale"
    return "down"


def record_success(
    db: Database,
    source: str,
    *,
    detail: str = "",
    at: datetime | None = None,
) -> None:
    now = at or datetime.now(tz=UTC)
    iso = now.isoformat()
    db.execute(
        "INSERT INTO source_freshness(source, status, last_success_at, last_attempt_at, detail) "
        "VALUES (?, 'ok', ?, ?, ?) "
        "ON CONFLICT(source) DO UPDATE SET "
        "status='ok', last_success_at=excluded.last_success_at, "
        "last_attempt_at=excluded.last_attempt_at, detail=excluded.detail",
        (source, iso, iso, detail),
    )


def record_attempt(
    db: Database,
    source: str,
    *,
    ok: bool,
    detail: str = "",
    at: datetime | None = None,
) -> None:
    now = at or datetime.now(tz=UTC)
    if ok:
        record_success(db, source, detail=detail, at=now)
        return
    iso = now.isoformat()
    rows = db.fetchall("SELECT last_success_at FROM source_freshness WHERE source = ?", (source,))
    last = rows[0]["last_success_at"] if rows else None
    status = _classify(source, last, now)
    if status == "ok":
        status = "stale"
    db.execute(
        "INSERT INTO source_freshness(source, status, last_success_at, last_attempt_at, detail) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(source) DO UPDATE SET "
        "status=excluded.status, last_attempt_at=excluded.last_attempt_at, detail=excluded.detail",
        (source, status, last, iso, detail),
    )


def ensure_defaults(db: Database) -> None:
    """Seed Schwab unknown + EDGAR unknown for dashboard."""
    now = datetime.now(tz=UTC).isoformat()
    for source, detail in (
        ("schwab", "OAuth not configured on this host — stub"),
        ("edgar", "awaiting ingest"),
    ):
        rows = db.fetchall("SELECT source FROM source_freshness WHERE source = ?", (source,))
        if not rows:
            db.execute(
                "INSERT INTO source_freshness(source, status, last_success_at, last_attempt_at, detail) "
                "VALUES (?, 'unknown', NULL, ?, ?)",
                (source, now, detail),
            )


def read_freshness(db: Database) -> list[FreshnessRow]:
    ensure_defaults(db)
    now = datetime.now(tz=UTC)
    rows = db.fetchall("SELECT * FROM source_freshness ORDER BY source")
    out: list[FreshnessRow] = []
    for r in rows:
        status = _classify(str(r["source"]), r["last_success_at"], now)
        # Preserve explicit unknown for never-succeeded Schwab
        if r["last_success_at"] is None and str(r["status"]) == "unknown":
            status = "unknown"
        out.append(
            FreshnessRow(
                source=str(r["source"]),
                status=status,
                last_success_at=r["last_success_at"],
                last_attempt_at=r["last_attempt_at"],
                detail=str(r["detail"] or ""),
            )
        )
    return out


def mark_edgar_fixture_ok(db: Database) -> None:
    record_success(db, "edgar", detail="fixture ingest ok")
