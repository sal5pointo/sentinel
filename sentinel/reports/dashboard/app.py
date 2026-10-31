"""Phase 2 FastAPI dashboard + approval mount + REST surface.

Paper mode. trading_enabled remains false. GET never places orders.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from sentinel import __version__
from sentinel.approval.server import router as approval_router
from sentinel.broker.paper_broker import PaperBroker
from sentinel.config import load_settings, resolve_trading_enabled
from sentinel.ops import killswitch
from sentinel.ops.freshness import ensure_defaults, read_freshness
from sentinel.planner.plan import list_plans
from sentinel.reports.dashboard.shell import shell as _shell
from sentinel.storage.db import Database

app = FastAPI(
    title="SENTINEL Dashboard",
    version=__version__,
    description="Phase 2 paper approval + dashboard. No live Schwab orders.",
)
app.include_router(approval_router)
app.state.paper_broker = PaperBroker(starting_cash=100_000.0)


def _db() -> Database:
    return Database()


@app.on_event("startup")
def _startup() -> None:
    db = _db()
    try:
        killswitch.load_from_db(db)
        ensure_defaults(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "trading_enabled": resolve_trading_enabled(),
        "read_only_live": True,
        "kill_state": killswitch.get_state().value,
        "mode": "paper",
        "phase": 2,
    }


# —— REST API for dashboard / iPhone shell ——


@app.get("/api/mode")
def api_mode() -> dict[str, Any]:
    return {
        "mode": "paper",
        "kill_state": killswitch.get_state().value,
        "kill_reason": killswitch.get_reason(),
        "trading_enabled": resolve_trading_enabled(),
        "chip": "Halted" if killswitch.get_state() == killswitch.KillState.HALT else "Paper",
    }


@app.post("/api/halt", response_model=None)
def api_halt(action: str = Form("halt"), reason: str = Form("api")) -> RedirectResponse:
    db = _db()
    try:
        if action == "resume":
            killswitch.resume()
        else:
            killswitch.halt(reason or "api")
        killswitch.persist(db)
        # Form posts from chrome redirect; JSON clients can use Accept
        return RedirectResponse(url="/halt", status_code=303)
    finally:
        db.close()


@app.post("/api/halt/json")
def api_halt_json(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    action = str(payload.get("action", "halt"))
    reason = str(payload.get("reason", "api"))
    db = _db()
    try:
        if action == "resume":
            killswitch.resume()
        else:
            killswitch.halt(reason)
        killswitch.persist(db)
        return {
            "kill_state": killswitch.get_state().value,
            "reason": killswitch.get_reason(),
        }
    finally:
        db.close()


@app.get("/api/freshness")
def api_freshness() -> list[dict[str, Any]]:
    db = _db()
    try:
        return [f.to_dict() for f in read_freshness(db)]
    finally:
        db.close()


@app.get("/api/positions")
def api_positions() -> dict[str, Any]:
    broker: PaperBroker = app.state.paper_broker
    account = broker.account_hash
    positions = broker.get_positions(account)
    bal = broker.get_balances(account)
    return {
        "account_hash": account,
        "balances": {
            "equity": bal.equity,
            "cash": bal.cash,
            "settled_cash": bal.settled_cash,
        },
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "average_price": p.average_price,
                "market_value": p.market_value,
            }
            for p in positions
        ],
        "source": "paper_broker",
    }


@app.get("/api/plans")
def api_plans(status: str | None = None) -> list[dict[str, Any]]:
    db = _db()
    try:
        return [p.to_dict() for p in list_plans(db, status=status)]
    finally:
        db.close()


@app.get("/api/plans/{plan_id}")
def api_plan_detail(plan_id: str) -> dict[str, Any]:
    from sentinel.planner.plan import get_plan

    db = _db()
    try:
        plan = get_plan(db, plan_id)
        if plan is None:
            return {"error": "not_found", "plan_id": plan_id}
        return plan.to_dict()
    finally:
        db.close()


@app.get("/api/signals")
def api_signals(limit: int = 50) -> list[dict[str, Any]]:
    db = _db()
    try:
        rows = db.fetchall(
            "SELECT symbol, family, direction, score, detail_json, as_of, created_at "
            "FROM signal_alerts ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        out = []
        for r in rows:
            out.append(
                {
                    "symbol": r["symbol"],
                    "family": r["family"],
                    "direction": r["direction"],
                    "score": r["score"],
                    "detail": json.loads(r["detail_json"] or "{}"),
                    "as_of": r["as_of"],
                    "created_at": r["created_at"],
                }
            )
        return out
    finally:
        db.close()


@app.get("/api/signals/freshness")
def api_signals_freshness() -> dict[str, Any]:
    db = _db()
    try:
        freshness = [f.to_dict() for f in read_freshness(db)]
        latest = db.fetchall(
            "SELECT MAX(created_at) AS last_alert FROM signal_alerts"
        )
        return {
            "sources": freshness,
            "last_alert_at": latest[0]["last_alert"] if latest else None,
            "mode": "paper",
        }
    finally:
        db.close()


# —— HTML pages ——


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    settings = load_settings()
    db = _db()
    try:
        killswitch.load_from_db(db)
        ensure_defaults(db)
        freshness = read_freshness(db)
        plans = list_plans(db, status="pending", limit=10)
        if not plans:
            plans = list_plans(db, limit=10)
        alerts = db.fetchall(
            "SELECT symbol, family, direction, score, as_of FROM signal_alerts "
            "ORDER BY id DESC LIMIT 8"
        )
        universe = db.fetchall(
            "SELECT member_count, as_of_month, stage FROM universe_snapshots "
            "ORDER BY as_of_month DESC LIMIT 1"
        )
    finally:
        db.close()

    broker: PaperBroker = app.state.paper_broker
    bal = broker.get_balances(broker.account_hash)
    positions = broker.get_positions(broker.account_hash)

    u_line = (
        f"{universe[0]['stage']} · {universe[0]['member_count']} names · {universe[0]['as_of_month']}"
        if universe
        else "not built"
    )
    fresh_html = "".join(
        f'<span><span class="dot {f.status}"></span>{f.source} · {f.status}</span>'
        for f in freshness
    )

    if plans:
        plan_html = "<table><thead><tr><th>Plan</th><th>Symbol</th><th>Qty</th><th>Status</th><th></th></tr></thead><tbody>"
        for p in plans:
            plan_html += (
                f"<tr><td class='mono'>{p.plan_id[:16]}</td><td>{p.symbol}</td>"
                f"<td class='mono'>{p.quantity:g}</td><td>{p.status}</td>"
                f"<td><a href='/plans/{p.plan_id}'>Review</a></td></tr>"
            )
        plan_html += "</tbody></table>"
    else:
        plan_html = "<p class='empty'>No plans yet. Run <span class='mono'>sentinel plan-demo</span>.</p>"

    if positions:
        pos_html = "<table><thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Mkt</th></tr></thead><tbody>"
        for p in positions:
            pos_html += (
                f"<tr><td>{p.symbol}</td>"
                f"<td class='mono'>{p.quantity}</td>"
                f"<td class='mono'>{p.average_price}</td>"
                f"<td class='mono'>{p.market_value}</td></tr>"
            )
        pos_html += "</tbody></table>"
    else:
        pos_html = "<p class='empty'>No paper positions.</p>"

    if alerts:
        alert_html = "<table><thead><tr><th>Symbol</th><th>Family</th><th>Score</th></tr></thead><tbody>"
        for a in alerts:
            alert_html += (
                f"<tr><td>{a['symbol']}</td><td>{a['family']}</td>"
                f"<td class='mono'>{a['score']}</td></tr>"
            )
        alert_html += "</tbody></table>"
    else:
        alert_html = "<p class='empty'>No scanner alerts.</p>"

    body = f"""
    <h1>Dashboard</h1>
    <p class="lede">Paper situational awareness — plans, positions, freshness.</p>
    <div class="metrics">
      <div><div class="metric-label">Equity</div><div class="metric-value">${bal.equity:,.0f}</div></div>
      <div><div class="metric-label">Cash</div><div class="metric-value">${bal.cash:,.0f}</div></div>
      <div><div class="metric-label">Universe</div><div class="metric-value" style="font-size:1rem">{u_line}</div></div>
      <div><div class="metric-label">trading_enabled</div><div class="metric-value" style="font-size:1rem">{"ON" if settings.trading_enabled else "OFF"}</div></div>
    </div>
    <section>
      <h2>Plans</h2>
      {plan_html}
    </section>
    <section>
      <h2>Positions</h2>
      {pos_html}
    </section>
    <section>
      <h2>Scanner alerts</h2>
      {alert_html}
    </section>
    <section>
      <h2>Freshness</h2>
      <div class="freshness">{fresh_html}</div>
    </section>
    """
    return _shell("Dashboard", body, halt_open=killswitch.get_state() == killswitch.KillState.HALT)


@app.get("/plans", response_class=HTMLResponse)
def plans_page() -> str:
    db = _db()
    try:
        plans = list_plans(db, limit=50)
    finally:
        db.close()
    rows = "".join(
        f"<tr><td class='mono'><a href='/plans/{p.plan_id}'>{p.plan_id}</a></td>"
        f"<td>{p.symbol}</td><td class='mono'>{p.quantity:g}</td>"
        f"<td>{p.status}</td><td class='mono'>{p.entry_ref_price}</td></tr>"
        for p in plans
    ) or "<tr><td colspan='5' class='empty'>No plans</td></tr>"
    body = f"""
    <h1>Plans</h1>
    <p class="lede">Open / pending / decided trade plans.</p>
    <table><thead><tr><th>ID</th><th>Symbol</th><th>Qty</th><th>Status</th><th>Ref</th></tr></thead>
    <tbody>{rows}</tbody></table>
    """
    return _shell("Plans", body, halt_open=killswitch.get_state() == killswitch.KillState.HALT)


@app.get("/plans/{plan_id}", response_class=HTMLResponse)
def plan_detail_page(plan_id: str) -> str:
    from sentinel.planner.plan import get_plan

    db = _db()
    try:
        plan = get_plan(db, plan_id)
    finally:
        db.close()
    if plan is None:
        return _shell("Plan", "<h1>Not found</h1>")
    body = f"""
    <h1>{plan.symbol}</h1>
    <p class="lede">Plan detail — confirm via tokenized email link or API.</p>
    <pre class="mono" style="white-space:pre-wrap;font-size:0.8rem">{json.dumps(plan.to_dict(), indent=2)}</pre>
    """
    return _shell("Plan", body, halt_open=killswitch.get_state() == killswitch.KillState.HALT)


@app.get("/positions", response_class=HTMLResponse)
def positions_page() -> str:
    data = api_positions()
    rows = "".join(
        f"<tr><td>{p['symbol']}</td><td class='mono'>{p['quantity']}</td>"
        f"<td class='mono'>{p['average_price']}</td><td class='mono'>{p['market_value']}</td></tr>"
        for p in data["positions"]
    ) or "<tr><td colspan='4' class='empty'>Flat</td></tr>"
    body = f"""
    <h1>Positions</h1>
    <p class="lede">Paper broker positions (live Schwab needs Windows OAuth).</p>
    <p class="mono">equity ${data['balances']['equity']:,.2f} · cash ${data['balances']['cash']:,.2f}</p>
    <table><thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Mkt</th></tr></thead>
    <tbody>{rows}</tbody></table>
    """
    return _shell("Positions", body, halt_open=killswitch.get_state() == killswitch.KillState.HALT)


@app.get("/status", response_class=HTMLResponse)
def status_page() -> str:
    db = _db()
    try:
        killswitch.load_from_db(db)
        freshness = [f.to_dict() for f in read_freshness(db)]
    finally:
        db.close()
    body = f"""
    <h1>Status</h1>
    <p class="lede">Ops: mode chip, kill state, freshness, trading gate.</p>
    <section>
      <h2>Mode</h2>
      <p>Paper · kill={killswitch.get_state().value} · trading_enabled={resolve_trading_enabled()}</p>
    </section>
    <section>
      <h2>Freshness JSON</h2>
      <pre class="mono" style="white-space:pre-wrap;font-size:0.8rem">{json.dumps(freshness, indent=2)}</pre>
    </section>
    """
    return _shell("Status", body, halt_open=killswitch.get_state() == killswitch.KillState.HALT)


@app.get("/halt", response_class=HTMLResponse)
def halt_page() -> str:
    state = killswitch.get_state().value
    body = f"""
    <h1>Kill switch</h1>
    <p class="lede">HALT blocks new entries. FLATTEN stays passkey + typed confirm (scaffolded later).</p>
    <p>Current state: <strong class="mono">{state}</strong></p>
    <form method="post" action="/halt" style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:1rem">
      <button class="btn btn-danger" type="submit" name="action" value="halt">Engage HALT</button>
      <button class="btn btn-ghost" type="submit" name="action" value="resume">Resume (local)</button>
    </form>
    """
    return _shell("Halt", body, halt_open=killswitch.get_state() == killswitch.KillState.HALT)


@app.post("/halt")
def halt_action(action: str = Form("halt")) -> RedirectResponse:
    db = _db()
    try:
        if action == "resume":
            killswitch.resume()
        else:
            killswitch.halt("dashboard")
        killswitch.persist(db)
    finally:
        db.close()
    return RedirectResponse(url="/halt", status_code=303)
