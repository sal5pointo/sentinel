"""TradePlan builder — numbers from code only; LLM may attach thesis text later."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sentinel.planner.funding import FundingCheck, check_settled_cash
from sentinel.planner.sizing import SizeResult, size_shares
from sentinel.risk.rules import RiskVerdict, check_plan_risk
from sentinel.risk.stops import StopSpec, stop_from_atr, stop_from_low52
from sentinel.storage.db import Database


@dataclass
class TradePlan:
    plan_id: str
    symbol: str
    side: str
    bucket: str
    quantity: float
    entry_ref_price: float
    stop_price: float
    risk_usd: float
    risk_pct: float
    status: str = "pending"
    entry_limit: float | None = None
    max_pos_pct: float | None = None
    families: list[str] = field(default_factory=list)
    score: float = 0.0
    funding: dict[str, Any] = field(default_factory=dict)
    numbers: dict[str, Any] = field(default_factory=dict)
    thesis: str = ""
    evidence: list[str] = field(default_factory=list)
    created_at: str = ""
    expires_at: str | None = None
    decided_at: str | None = None
    decision: str | None = None
    decision_reason: str | None = None
    executed_at: str | None = None
    broker_order_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def locked_numbers(self) -> dict[str, Any]:
        """Numeric fields that hostile untrusted text must not change."""
        return dict(self.numbers)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def build_trade_plan(
    *,
    symbol: str,
    entry: float,
    atr: float,
    equity: float,
    settled_cash: float,
    bucket: str = "A",
    side: str = "BUY",
    families: list[str] | None = None,
    score: float = 0.0,
    low_52w: float | None = None,
    open_positions: int = 0,
    portfolio_heat_pct: float = 0.0,
    day_start_equity: float | None = None,
    peak_equity: float | None = None,
    evidence: list[str] | None = None,
    thesis: str = "",
    ttl_hours: float = 8.0,
) -> tuple[TradePlan, RiskVerdict, FundingCheck, SizeResult, StopSpec]:
    """Build a plan from market numbers. Requires confluence families already filtered."""
    fams = list(families or [])
    if bucket.upper() == "G" and low_52w is not None:
        stop_spec = stop_from_low52(entry=entry, low_52w=low_52w, atr=atr)
    else:
        stop_spec = stop_from_atr(entry=entry, atr=atr, side=side, bucket=bucket)

    sized = size_shares(equity=equity, entry=entry, stop=stop_spec.stop_price, bucket=bucket)
    day0 = day_start_equity if day_start_equity is not None else equity
    peak = peak_equity if peak_equity is not None else equity
    verdict = check_plan_risk(
        symbol=symbol,
        bucket=bucket,
        notional=sized.notional,
        equity=equity,
        open_positions=open_positions,
        portfolio_heat_pct=portfolio_heat_pct,
        day_start_equity=day0,
        peak_equity=peak,
    )
    qty = sized.quantity
    if verdict.half_size and qty >= 2:
        qty = float(int(qty // 2))
    funding = check_settled_cash(
        settled_cash=settled_cash,
        equity=equity,
        notional=qty * entry,
    )
    status = "pending"
    if qty < 1:
        status = "blocked"
    if not verdict.ok or not funding.ok:
        status = "blocked"

    now = _now()
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    numbers = {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "bucket": bucket.upper(),
        "quantity": qty,
        "entry_ref_price": entry,
        "stop_price": stop_spec.stop_price,
        "risk_usd": sized.risk_usd,
        "risk_pct": sized.risk_pct,
        "max_pos_pct": sized.max_pos_pct,
        "atr": atr,
        "score": score,
        "notional": round(qty * entry, 2),
    }
    plan = TradePlan(
        plan_id=plan_id,
        symbol=symbol.upper(),
        side=side.upper(),
        bucket=bucket.upper(),
        quantity=qty,
        entry_ref_price=entry,
        entry_limit=entry,
        stop_price=stop_spec.stop_price,
        risk_usd=sized.risk_usd,
        risk_pct=sized.risk_pct,
        max_pos_pct=sized.max_pos_pct,
        families=fams,
        score=score,
        status=status,
        funding=funding.to_dict(),
        numbers=numbers,
        thesis=thesis,
        evidence=list(evidence or []),
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=ttl_hours)).isoformat(),
    )
    return plan, verdict, funding, sized, stop_spec


def persist_plan(db: Database, plan: TradePlan) -> None:
    db.execute(
        """
        INSERT INTO trade_plans(
            plan_id, symbol, side, bucket, quantity, entry_ref_price, entry_limit,
            stop_price, risk_usd, risk_pct, max_pos_pct, families_json, score, status,
            funding_json, numbers_json, thesis, evidence_json, created_at, expires_at,
            decided_at, decision, decision_reason, executed_at, broker_order_ids_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(plan_id) DO UPDATE SET
            status=excluded.status,
            quantity=excluded.quantity,
            numbers_json=excluded.numbers_json,
            funding_json=excluded.funding_json,
            thesis=excluded.thesis,
            decided_at=excluded.decided_at,
            decision=excluded.decision,
            decision_reason=excluded.decision_reason,
            executed_at=excluded.executed_at,
            broker_order_ids_json=excluded.broker_order_ids_json
        """,
        (
            plan.plan_id,
            plan.symbol,
            plan.side,
            plan.bucket,
            plan.quantity,
            plan.entry_ref_price,
            plan.entry_limit,
            plan.stop_price,
            plan.risk_usd,
            plan.risk_pct,
            plan.max_pos_pct,
            json.dumps(plan.families),
            plan.score,
            plan.status,
            json.dumps(plan.funding),
            json.dumps(plan.numbers),
            plan.thesis,
            json.dumps(plan.evidence),
            plan.created_at,
            plan.expires_at,
            plan.decided_at,
            plan.decision,
            plan.decision_reason,
            plan.executed_at,
            json.dumps(plan.broker_order_ids),
        ),
    )


def _row_to_plan(row: Any) -> TradePlan:
    return TradePlan(
        plan_id=str(row["plan_id"]),
        symbol=str(row["symbol"]),
        side=str(row["side"]),
        bucket=str(row["bucket"]),
        quantity=float(row["quantity"]),
        entry_ref_price=float(row["entry_ref_price"]),
        entry_limit=float(row["entry_limit"]) if row["entry_limit"] is not None else None,
        stop_price=float(row["stop_price"]),
        risk_usd=float(row["risk_usd"]),
        risk_pct=float(row["risk_pct"]),
        max_pos_pct=float(row["max_pos_pct"]) if row["max_pos_pct"] is not None else None,
        families=json.loads(row["families_json"] or "[]"),
        score=float(row["score"] or 0),
        status=str(row["status"]),
        funding=json.loads(row["funding_json"] or "{}"),
        numbers=json.loads(row["numbers_json"] or "{}"),
        thesis=str(row["thesis"] or ""),
        evidence=json.loads(row["evidence_json"] or "[]"),
        created_at=str(row["created_at"]),
        expires_at=str(row["expires_at"]) if row["expires_at"] else None,
        decided_at=str(row["decided_at"]) if row["decided_at"] else None,
        decision=str(row["decision"]) if row["decision"] else None,
        decision_reason=str(row["decision_reason"]) if row["decision_reason"] else None,
        executed_at=str(row["executed_at"]) if row["executed_at"] else None,
        broker_order_ids=json.loads(row["broker_order_ids_json"] or "[]"),
    )


def get_plan(db: Database, plan_id: str) -> TradePlan | None:
    rows = db.fetchall("SELECT * FROM trade_plans WHERE plan_id = ?", (plan_id,))
    if not rows:
        return None
    return _row_to_plan(rows[0])


def list_plans(db: Database, *, status: str | None = None, limit: int = 50) -> list[TradePlan]:
    if status:
        rows = db.fetchall(
            "SELECT * FROM trade_plans WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        )
    else:
        rows = db.fetchall(
            "SELECT * FROM trade_plans ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    return [_row_to_plan(r) for r in rows]


def update_plan_status(
    db: Database,
    plan: TradePlan,
    *,
    status: str,
    decision: str | None = None,
    reason: str | None = None,
) -> TradePlan:
    plan.status = status
    plan.decision = decision
    plan.decision_reason = reason
    plan.decided_at = _now().isoformat()
    persist_plan(db, plan)
    return plan
