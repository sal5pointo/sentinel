"""Paper executor: preview → bracket → reconcile. Idempotent on plan_id.

Live Schwab path stays blocked while trading_enabled is false.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sentinel.broker.base import BrokerClient, OrderResult, TradingDisabledError
from sentinel.broker.order_builder import build_bracket_order
from sentinel.broker.paper_broker import PaperBroker
from sentinel.config import resolve_trading_enabled
from sentinel.execution.reconcile import persist_order_row, reconcile_paper
from sentinel.logging_setup import get_logger
from sentinel.ops import killswitch
from sentinel.ops.audit import AuditLog
from sentinel.planner.plan import TradePlan, get_plan, persist_plan
from sentinel.risk.rules import drift_blocks_confirm
from sentinel.storage.db import Database

log = get_logger("execution.executor")


@dataclass
class ExecutionResult:
    ok: bool
    plan_id: str
    status: str
    preview: dict[str, Any] | None = None
    entry_order: dict[str, Any] | None = None
    stop_order: dict[str, Any] | None = None
    reconcile: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Executor:
    def __init__(
        self,
        db: Database,
        broker: BrokerClient,
        *,
        max_drift_pct: float = 1.0,
        audit: AuditLog | None = None,
    ) -> None:
        self.db = db
        self.broker = broker
        self.max_drift_pct = max_drift_pct
        self.audit = audit or AuditLog(db=db)

    def _acquire_lock(self, plan_id: str) -> bool:
        now = datetime.now(tz=UTC).isoformat()
        rows = self.db.fetchall("SELECT state FROM execution_locks WHERE plan_id = ?", (plan_id,))
        if rows:
            state = str(rows[0]["state"])
            if state in {"executing", "executed"}:
                return False
        self.db.execute(
            """
            INSERT INTO execution_locks(plan_id, state, created_at, updated_at, detail_json)
            VALUES (?, 'executing', ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET state='executing', updated_at=excluded.updated_at
            """,
            (plan_id, now, now, json.dumps({})),
        )
        return True

    def _finish_lock(self, plan_id: str, state: str, detail: dict[str, Any]) -> None:
        now = datetime.now(tz=UTC).isoformat()
        self.db.execute(
            "UPDATE execution_locks SET state=?, updated_at=?, detail_json=? WHERE plan_id=?",
            (state, now, json.dumps(detail, default=str), plan_id),
        )

    def execute_approved_plan(
        self,
        plan_id: str,
        *,
        live_price: float | None = None,
        half_size: bool = False,
    ) -> ExecutionResult:
        plan = get_plan(self.db, plan_id)
        if plan is None:
            return ExecutionResult(ok=False, plan_id=plan_id, status="missing", reasons=["plan_not_found"])

        # Idempotency: already executed
        if plan.status == "executed" or plan.broker_order_ids:
            return ExecutionResult(
                ok=True,
                plan_id=plan_id,
                status="already_executed",
                entry_order={"order_ids": plan.broker_order_ids},
                reasons=["idempotent_replay"],
            )

        if plan.status not in {"approved", "pending"}:
            return ExecutionResult(
                ok=False, plan_id=plan_id, status=plan.status, reasons=["not_approved"]
            )

        if killswitch.get_state() == killswitch.KillState.HALT:
            return ExecutionResult(ok=False, plan_id=plan_id, status="halted", reasons=["killswitch_halt"])

        if not isinstance(self.broker, PaperBroker) and not resolve_trading_enabled():
            raise TradingDisabledError(
                "Live broker execution blocked: trading_enabled is false. PaperBroker only."
            )

        if not self._acquire_lock(plan_id):
            return ExecutionResult(
                ok=True, plan_id=plan_id, status="locked_or_done", reasons=["idempotent_lock"]
            )

        qty = plan.quantity
        if half_size:
            qty = float(max(1, int(qty // 2))) if qty >= 2 else qty

        px = live_price
        if px is None:
            quotes = self.broker.get_quotes([plan.symbol])
            px = quotes[0].ask or quotes[0].last
        if px is None:
            self._finish_lock(plan_id, "failed", {"reason": "no_quote"})
            return ExecutionResult(ok=False, plan_id=plan_id, status="no_quote", reasons=["no_quote"])

        blocked, drift = drift_blocks_confirm(
            planned_price=plan.entry_ref_price,
            live_price=float(px),
            max_drift_pct=self.max_drift_pct,
        )
        if blocked:
            self._finish_lock(plan_id, "drift_blocked", {"drift_pct": drift})
            return ExecutionResult(
                ok=False,
                plan_id=plan_id,
                status="drift_blocked",
                reasons=[f"price_drift_{drift}"],
            )

        order = build_bracket_order(
            symbol=plan.symbol,
            side=plan.side,
            quantity=qty,
            stop_price=plan.stop_price,
            limit_price=plan.entry_limit,
            plan_id=plan.plan_id,
        )
        account = self.broker.get_accounts()[0].account_hash
        preview = self.broker.preview_order(account, order)
        self.audit.record(
            "execution",
            "preview",
            {"plan_id": plan_id, "preview": preview.raw},
            actor="executor",
        )

        # Place entry fill on paper; attach stop child row
        entry_result = self._place_paper_bracket(account, plan, order, preview)

        plan.status = "executed"
        plan.executed_at = datetime.now(tz=UTC).isoformat()
        plan.broker_order_ids = [
            entry_result["entry"]["order_id"],
            entry_result["stop"]["order_id"],
        ]
        persist_plan(self.db, plan)

        report = reconcile_paper(self.db, self.broker, account_hash=account, plan_id=plan_id)
        self._finish_lock(plan_id, "executed", entry_result)
        self.audit.record(
            "execution",
            "filled",
            {"plan_id": plan_id, "orders": plan.broker_order_ids},
            actor="executor",
        )
        return ExecutionResult(
            ok=True,
            plan_id=plan_id,
            status="executed",
            preview={"order_id": preview.order_id, "status": preview.status, "raw": preview.raw},
            entry_order=entry_result["entry"],
            stop_order=entry_result["stop"],
            reconcile=report.to_dict(),
        )

    def _place_paper_bracket(
        self,
        account: str,
        plan: TradePlan,
        order: Any,
        preview: OrderResult,
    ) -> dict[str, Any]:
        # Entry: market/limit via paper place_order
        from sentinel.broker.base import OrderRequest

        entry_req = OrderRequest(
            symbol=plan.symbol,
            side=plan.side,
            quantity=order.quantity,
            order_type="LIMIT" if plan.entry_limit else "MARKET",
            limit_price=plan.entry_limit,
            plan_id=plan.plan_id,
            extra={"role": "entry", "preview_id": preview.order_id},
        )
        filled = self.broker.place_order(account, entry_req)
        fill_px = float(filled.raw.get("fill_price") or 0)
        persist_order_row(
            self.db,
            order_id=filled.order_id,
            plan_id=plan.plan_id,
            role="entry",
            symbol=plan.symbol,
            side=plan.side,
            quantity=order.quantity,
            order_type=entry_req.order_type,
            status=filled.status,
            limit_price=plan.entry_limit,
            fill_price=fill_px,
            raw=filled.raw,
        )
        if fill_px:
            self.db.execute(
                "INSERT INTO paper_fills(order_id, plan_id, symbol, quantity, fill_price, filled_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    filled.order_id,
                    plan.plan_id,
                    plan.symbol,
                    order.quantity,
                    fill_px,
                    datetime.now(tz=UTC).isoformat(),
                ),
            )

        stop_side = "SELL" if plan.side.upper() == "BUY" else "BUY"
        stop_id = f"stop-{filled.order_id}"
        persist_order_row(
            self.db,
            order_id=stop_id,
            plan_id=plan.plan_id,
            role="stop",
            symbol=plan.symbol,
            side=stop_side,
            quantity=order.quantity,
            order_type="STOP",
            status="WORKING_GTC",
            stop_price=plan.stop_price,
            raw={"parent": filled.order_id, "duration": "GTC"},
        )
        return {
            "entry": {"order_id": filled.order_id, "status": filled.status, "fill_price": fill_px},
            "stop": {"order_id": stop_id, "status": "WORKING_GTC", "stop_price": plan.stop_price},
        }
