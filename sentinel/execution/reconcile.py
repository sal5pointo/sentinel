"""Reconcile paper orders vs broker state (paper only in Phase 2)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sentinel.broker.base import BrokerClient
from sentinel.storage.db import Database


@dataclass
class ReconcileReport:
    plan_id: str | None
    ok: bool
    mismatches: list[str] = field(default_factory=list)
    broker_positions: list[dict[str, Any]] = field(default_factory=list)
    db_orders: list[dict[str, Any]] = field(default_factory=list)
    as_of: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reconcile_paper(
    db: Database,
    broker: BrokerClient,
    *,
    account_hash: str,
    plan_id: str | None = None,
) -> ReconcileReport:
    now = datetime.now(tz=UTC).isoformat()
    if plan_id:
        rows = db.fetchall("SELECT * FROM paper_orders WHERE plan_id = ?", (plan_id,))
    else:
        rows = db.fetchall("SELECT * FROM paper_orders ORDER BY created_at DESC LIMIT 100")
    positions = broker.get_positions(account_hash)
    mismatches: list[str] = []

    filled_by_sym: dict[str, float] = {}
    for r in rows:
        if str(r["status"]) == "FILLED" and str(r["role"]) == "entry":
            sym = str(r["symbol"])
            side = str(r["side"]).upper()
            qty = float(r["quantity"])
            filled_by_sym[sym] = filled_by_sym.get(sym, 0.0) + (qty if side == "BUY" else -qty)

    pos_by_sym = {p.symbol: p.quantity for p in positions}
    for sym, qty in filled_by_sym.items():
        broker_qty = pos_by_sym.get(sym, 0.0)
        if abs(broker_qty - qty) > 1e-6:
            mismatches.append(f"{sym}: db_net={qty} broker={broker_qty}")

    return ReconcileReport(
        plan_id=plan_id,
        ok=len(mismatches) == 0,
        mismatches=mismatches,
        broker_positions=[{"symbol": p.symbol, "quantity": p.quantity} for p in positions],
        db_orders=[dict(r) for r in rows],
        as_of=now,
    )


def persist_order_row(
    db: Database,
    *,
    order_id: str,
    plan_id: str,
    role: str,
    symbol: str,
    side: str,
    quantity: float,
    order_type: str,
    status: str,
    limit_price: float | None = None,
    stop_price: float | None = None,
    fill_price: float | None = None,
    raw: dict[str, Any] | None = None,
) -> None:
    now = datetime.now(tz=UTC).isoformat()
    db.execute(
        """
        INSERT INTO paper_orders(
            order_id, plan_id, role, symbol, side, quantity, order_type,
            limit_price, stop_price, status, fill_price, created_at, updated_at, raw_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(order_id) DO UPDATE SET
            status=excluded.status,
            fill_price=excluded.fill_price,
            updated_at=excluded.updated_at,
            raw_json=excluded.raw_json
        """,
        (
            order_id,
            plan_id,
            role,
            symbol,
            side,
            quantity,
            order_type,
            limit_price,
            stop_price,
            status,
            fill_price,
            now,
            now,
            json.dumps(raw or {}, default=str),
        ),
    )
