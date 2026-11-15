"""Approval FastAPI routes — tokenized plan links; GET never executes.

Mounted into the dashboard app. Confirm requires POST + WebAuthn (or explicit
insecure bypass for offline tests only).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from sentinel.approval.tokens import issue_token, validate_token
from sentinel.approval.webauthn import REGISTRY, insecure_bypass_enabled
from sentinel.broker.base import Quote
from sentinel.broker.paper_broker import PaperBroker
from sentinel.config import load_settings, resolve_trading_enabled
from sentinel.execution.executor import Executor
from sentinel.ops import killswitch
from sentinel.ops.audit import AuditLog
from sentinel.planner.plan import get_plan, update_plan_status
from sentinel.reports.dashboard.shell import shell as _shell
from sentinel.risk.rules import drift_blocks_confirm
from sentinel.storage.db import Database

router = APIRouter(tags=["approval"])


def _db() -> Database:
    return Database()


def _max_drift() -> float:
    settings = load_settings()
    approval = getattr(settings, "approval", None)
    if isinstance(approval, dict):
        return float(approval.get("max_price_drift_pct", 1.0))
    raw = os.environ.get("SENTINEL_MAX_DRIFT_PCT")
    return float(raw) if raw else 1.0


@router.get("/p/{plan_id}", response_class=HTMLResponse)
def confirm_page(
    plan_id: str,
    t: str = "",
    action: str = "approve",
) -> HTMLResponse:
    """GET confirm page — never executes, never consumes token."""
    db = _db()
    try:
        plan = get_plan(db, plan_id)
        token = validate_token(db, t, consume=False) if t else None
        killswitch.load_from_db(db)
    finally:
        db.close()

    if plan is None:
        body = "<h1>Plan not found</h1><p class='err'>Unknown plan_id.</p>"
        return HTMLResponse(body, status_code=404)

    token_ok = token is not None and token.ok and token.plan_id == plan_id
    token_msg = ""
    if t and not token_ok:
        token_msg = f"<p class='err'>Token invalid: {token.reason if token else 'missing'}</p>"

    bypass_note = (
        "<p class='warn'>INSECURE WebAuthn bypass enabled (test only).</p>"
        if insecure_bypass_enabled()
        else ""
    )
    challenge = REGISTRY.begin_assertion()
    disabled = "disabled" if not token_ok else ""
    body = f"""
    <div class="approve-wrap">
      <h1>Approve plan</h1>
      <p class="lede">GET never executes. Confirm posts with passkey.</p>
      {token_msg}{bypass_note}
      <p class="line">{plan.side} {plan.quantity:g} {plan.symbol}</p>
      <p class="line">ref ${plan.entry_ref_price:.2f} · stop ${plan.stop_price:.2f}</p>
      <p class="line">risk ${plan.risk_usd:.2f} ({plan.risk_pct}%) · bucket {plan.bucket}</p>
      <p class="line">status {plan.status} · score {plan.score}</p>
      <p class="thesis">{plan.thesis or "Thesis pending (LLM memo optional)."}</p>
      <p class="line">Families: {", ".join(plan.families) or "—"}</p>
      <form method="post" action="/p/{plan.plan_id}/confirm">
        <input type="hidden" name="t" value="{t}"/>
        <input type="hidden" name="action" value="{action}"/>
        <input type="hidden" name="challenge" value="{challenge.get("challenge", "")}"/>
        <input type="hidden" name="credential_id" value=""/>
        <input type="hidden" name="assertion" value=""/>
        <input type="hidden" name="live_price" value="{plan.entry_ref_price}"/>
        <label>Decision
          <select name="decision">
            <option value="approve">Approve</option>
            <option value="half">Half size</option>
            <option value="reject">Reject</option>
            <option value="snooze">Snooze</option>
          </select>
        </label>
        <div style="margin-top:1rem;display:flex;gap:0.5rem;flex-wrap:wrap">
          <button class="btn btn-signal" type="submit" {disabled}>
            Confirm with passkey
          </button>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(
        _shell(
            "Approve",
            body,
            halt_open=killswitch.get_state() == killswitch.KillState.HALT,
        )
    )


@router.post("/p/{plan_id}/confirm", response_model=None)
async def confirm_post(
    plan_id: str,
    request: Request,
    t: str = Form(""),
    decision: str = Form("approve"),
    challenge: str = Form(""),
    credential_id: str = Form(""),
    assertion: str = Form(""),
    live_price: float = Form(0.0),
) -> HTMLResponse:
    db = _db()
    audit = AuditLog(db=db)
    try:
        token = validate_token(db, t, consume=False)
        if not token.ok or token.plan_id != plan_id:
            return HTMLResponse(
                f"<h1>Blocked</h1><p class='err'>Token: {token.reason}</p>",
                status_code=403,
            )

        ok_wa, wa_reason = REGISTRY.verify_assertion(
            credential_id=credential_id or None,
            client_challenge=challenge or None,
            assertion_b64=assertion or ("bypass" if insecure_bypass_enabled() else None),
        )
        if not ok_wa:
            audit.record("approval", "webauthn_failed", {"plan_id": plan_id, "reason": wa_reason})
            return HTMLResponse(
                f"<h1>Passkey required</h1><p class='err'>{wa_reason}</p>",
                status_code=401,
            )

        # Consume token only after passkey ok (single-use)
        consumed = validate_token(db, t, consume=True)
        if not consumed.ok:
            return HTMLResponse(
                f"<h1>Blocked</h1><p class='err'>Token: {consumed.reason}</p>",
                status_code=403,
            )

        plan = get_plan(db, plan_id)
        if plan is None:
            return HTMLResponse("<h1>Missing plan</h1>", status_code=404)

        if decision in {"reject", "snooze"}:
            update_plan_status(db, plan, status="rejected" if decision == "reject" else "snoozed", decision=decision)
            audit.record("approval", decision, {"plan_id": plan_id})
            return HTMLResponse(f"<h1>Recorded</h1><p>{decision}</p>")

        px = live_price or plan.entry_ref_price
        blocked, drift = drift_blocks_confirm(
            planned_price=plan.entry_ref_price,
            live_price=float(px),
            max_drift_pct=_max_drift(),
        )
        if blocked:
            audit.record("approval", "drift_blocked", {"plan_id": plan_id, "drift": drift})
            return HTMLResponse(
                f"<h1>Price drift</h1><p class='err'>Drift {drift}% — request re-plan.</p>",
                status_code=409,
            )

        if killswitch.get_state() == killswitch.KillState.HALT:
            return HTMLResponse("<h1>HALT</h1><p class='err'>Kill switch engaged.</p>", status_code=423)

        update_plan_status(db, plan, status="approved", decision=decision)
        audit.record(
            "approval",
            "approved",
            {"plan_id": plan_id, "decision": decision, "trading_enabled": resolve_trading_enabled()},
            actor="owner",
        )

        # Paper execute only — never live Schwab from this path while trading_enabled false
        broker = getattr(request.app.state, "paper_broker", None)
        if not isinstance(broker, PaperBroker):
            broker = PaperBroker()
            request.app.state.paper_broker = broker
        broker.seed_quote(
            Quote(
                symbol=plan.symbol,
                last=float(px),
                bid=float(px) * 0.999,
                ask=float(px) * 1.001,
            )
        )

        ex = Executor(db, broker, max_drift_pct=_max_drift(), audit=audit)
        result = ex.execute_approved_plan(
            plan_id,
            live_price=float(px),
            half_size=(decision == "half"),
        )
        status = 200 if result.ok else 409
        return HTMLResponse(
            f"<h1>{'Confirmed' if result.ok else 'Blocked'}</h1>"
            f"<pre class='mono'>{result.to_dict()}</pre>",
            status_code=status,
        )
    finally:
        db.close()


@router.get("/api/webauthn/register/options")
def webauthn_register_options() -> dict[str, Any]:
    return REGISTRY.begin_registration()


@router.post("/api/webauthn/register")
async def webauthn_register(payload: dict[str, Any]) -> dict[str, Any]:
    REGISTRY.finish_registration(
        user_id=str(payload.get("user_id", "owner")),
        credential_id=str(payload.get("credential_id", "cred-dev")),
        public_key_pem=str(payload.get("public_key_pem", "stub")),
    )
    return {"status": "registered"}


@router.get("/api/webauthn/assert/options")
def webauthn_assert_options() -> dict[str, Any]:
    return REGISTRY.begin_assertion()


def issue_plan_link(db: Database, plan_id: str, *, base_url: str = "http://127.0.0.1:8787") -> str:
    tok = issue_token(db, plan_id)
    return f"{base_url}/p/{plan_id}?t={tok.raw_token}"
