"""Phase 1 FastAPI dashboard — read-only shell aligned with design system.

No order execution. HALT chrome calls killswitch stub via POST.
Paper mode chip. trading_enabled remains false.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from sentinel import __version__
from sentinel.config import load_settings, resolve_trading_enabled
from sentinel.ops import killswitch
from sentinel.ops.freshness import ensure_defaults, read_freshness
from sentinel.storage.db import Database

app = FastAPI(
    title="SENTINEL Dashboard",
    version=__version__,
    description="Phase 1 read-only shell. No trading endpoints.",
)

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Syne:wght@600;700&display=swap');
:root {
  --sentinel-bg: #e6ebf0;
  --sentinel-bg-elevated: #f3f6f8;
  --sentinel-bg-sunken: #d5dde6;
  --sentinel-ink: #12181f;
  --sentinel-ink-muted: #4a5560;
  --sentinel-ink-faint: #7a8692;
  --sentinel-line: color-mix(in srgb, var(--sentinel-ink) 12%, transparent);
  --sentinel-wash-1: radial-gradient(120% 80% at 10% -10%, #c5d8e4 0%, transparent 55%);
  --sentinel-wash-2: radial-gradient(90% 70% at 100% 0%, #d7e4dc 0%, transparent 50%);
  --sentinel-wash-3: linear-gradient(165deg, #e6ebf0 0%, #dfe6ec 45%, #d8e0e8 100%);
  --sentinel-grid:
    linear-gradient(color-mix(in srgb, var(--sentinel-ink) 4%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--sentinel-ink) 4%, transparent) 1px, transparent 1px);
  --sentinel-grid-size: 24px 24px;
  --sentinel-signal: #0f766e;
  --sentinel-signal-ink: #f3fffc;
  --sentinel-signal-hover: #0d5f59;
  --sentinel-caution: #b45309;
  --sentinel-caution-bg: #fef3c7;
  --sentinel-danger: #b91c1c;
  --sentinel-danger-ink: #fff7f7;
  --sentinel-positive: #047857;
  --sentinel-negative: #b91c1c;
  --sentinel-mode-paper: #0f766e;
  --sentinel-mode-halt: #b91c1c;
  --font-display: "Syne", "Segoe UI", sans-serif;
  --font-ui: "Figtree", "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", "SF Mono", ui-monospace, monospace;
  --page-pad: clamp(1rem, 3vw, 2rem);
  --content-max: 72rem;
  --radius-md: 8px;
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --dur-med: 220ms;
  --dur-slow: 400ms;
}
@media (prefers-reduced-motion: reduce) {
  :root { --dur-med: 0ms; --dur-slow: 0ms; }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: var(--font-ui);
  color: var(--sentinel-ink);
  background:
    var(--sentinel-wash-1),
    var(--sentinel-wash-2),
    var(--sentinel-wash-3);
  background-color: var(--sentinel-bg);
  min-height: 100vh;
}
body::before {
  content: "";
  position: fixed; inset: 0;
  background-image: var(--sentinel-grid);
  background-size: var(--sentinel-grid-size);
  pointer-events: none;
  opacity: 0.55;
  z-index: 0;
}
.shell { position: relative; z-index: 1; max-width: var(--content-max); margin: 0 auto; padding: 0 var(--page-pad) 3rem; }
.chrome {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: 0.85rem 0;
  background: color-mix(in srgb, var(--sentinel-bg) 88%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--sentinel-line);
}
.brand {
  font-family: var(--font-display);
  font-weight: 700;
  letter-spacing: 0.08em;
  font-size: 1.15rem;
  text-decoration: none;
  color: var(--sentinel-ink);
}
.chrome-right { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.chip {
  font-size: 0.75rem; font-weight: 600; letter-spacing: 0.04em;
  padding: 0.3rem 0.55rem; border-radius: 4px;
  border: 1px solid var(--sentinel-line);
  background: var(--sentinel-bg-elevated);
}
.chip.paper { color: var(--sentinel-mode-paper); border-color: color-mix(in srgb, var(--sentinel-mode-paper) 35%, transparent); }
.chip.halted { color: var(--sentinel-danger-ink); background: var(--sentinel-danger); border-color: var(--sentinel-danger); }
.chip.auth { color: var(--sentinel-caution); background: var(--sentinel-caution-bg); }
.btn {
  font-family: var(--font-ui); font-weight: 600; font-size: 0.85rem;
  border: none; border-radius: var(--radius-md); cursor: pointer;
  padding: 0.45rem 0.85rem; min-height: 44px;
  transition: background var(--dur-med) var(--ease-out);
}
.btn-danger { background: var(--sentinel-danger); color: var(--sentinel-danger-ink); }
.btn-danger:hover { filter: brightness(0.95); }
.btn-ghost { background: transparent; color: var(--sentinel-ink-muted); border: 1px solid var(--sentinel-line); }
.halt-curtain {
  height: 0; overflow: hidden;
  background: var(--sentinel-danger); color: var(--sentinel-danger-ink);
  font-size: 0.85rem; font-weight: 600; text-align: center;
  transition: height var(--dur-slow) var(--ease-out);
}
.halt-curtain.open { height: 2rem; line-height: 2rem; }
h1 { font-family: var(--font-display); font-size: clamp(1.5rem, 3vw, 2rem); margin: 1.5rem 0 0.35rem; }
.lede { color: var(--sentinel-ink-muted); margin: 0 0 1.5rem; max-width: 40rem; }
.metrics {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem;
  padding: 1rem 0 1.25rem; border-bottom: 1px solid var(--sentinel-line);
  margin-bottom: 1.5rem;
}
@media (max-width: 639px) { .metrics { grid-template-columns: repeat(2, 1fr); } }
.metric-label { font-size: 0.75rem; color: var(--sentinel-ink-faint); text-transform: uppercase; letter-spacing: 0.06em; }
.metric-value { font-family: var(--font-mono); font-size: clamp(1.25rem, 2.5vw, 1.75rem); font-weight: 500; margin-top: 0.2rem; }
section { margin-bottom: 2rem; }
section h2 {
  font-family: var(--font-display); font-size: 1.15rem; margin: 0 0 0.75rem;
  letter-spacing: 0.02em;
}
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { text-align: left; padding: 0.55rem 0.35rem; border-bottom: 1px solid var(--sentinel-line); }
th { color: var(--sentinel-ink-faint); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.mono { font-family: var(--font-mono); }
.freshness { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; }
.dot { width: 0.55rem; height: 0.55rem; border-radius: 50%; display: inline-block; margin-right: 0.35rem; }
.dot.ok { background: var(--sentinel-positive); }
.dot.stale { background: var(--sentinel-caution); }
.dot.down, .dot.unknown { background: var(--sentinel-ink-faint); }
.footer-trust {
  margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--sentinel-line);
  color: var(--sentinel-ink-faint); font-size: 0.8rem;
}
nav.sub { display: flex; gap: 1rem; margin: 0.5rem 0 0; font-size: 0.9rem; }
nav.sub a { color: var(--sentinel-signal); text-decoration: none; }
.empty { color: var(--sentinel-ink-muted); font-size: 0.95rem; }
"""


def _db() -> Database:
    return Database()


def _mode_chip() -> tuple[str, str]:
    if killswitch.get_state() == killswitch.KillState.HALT:
        return "Halted", "halted"
    return "Paper", "paper"


def _shell(title: str, body: str, *, halt_open: bool = False) -> str:
    mode_label, mode_class = _mode_chip()
    trading = resolve_trading_enabled()
    auth_chip = (
        '<span class="chip auth">Auth: needs Windows OAuth</span>'
        if not trading
        else '<span class="chip">Auth</span>'
    )
    curtain_class = "halt-curtain open" if halt_open else "halt-curtain"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title} · SENTINEL</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="{curtain_class}">HALT — reduce-only · no new entries</div>
  <div class="shell">
    <header class="chrome">
      <a class="brand" href="/">SENTINEL</a>
      <div class="chrome-right">
        <span class="chip {mode_class}">{mode_label}</span>
        {auth_chip}
        <form method="post" action="/halt" style="margin:0">
          <button class="btn btn-danger" type="submit" name="action" value="halt">HALT</button>
        </form>
      </div>
    </header>
    <nav class="sub">
      <a href="/">Dashboard</a>
      <a href="/status">Status</a>
      <a href="/halt">Kill switch</a>
      <a href="/health">Health</a>
    </nav>
    {body}
    <p class="footer-trust">Decision support only — you approve every trade. trading_enabled remains false until Phase 4.</p>
  </div>
</body>
</html>"""


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "trading_enabled": resolve_trading_enabled(),
        "read_only": True,
        "kill_state": killswitch.get_state().value,
        "mode": "paper",
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    settings = load_settings()
    db = _db()
    try:
        killswitch.load_from_db(db)
        ensure_defaults(db)
        freshness = read_freshness(db)
        positions = db.fetchall(
            "SELECT symbol, quantity, average_price, market_value FROM positions_snapshot "
            "ORDER BY id DESC LIMIT 20"
        )
        # Deduplicate by symbol keeping first
        seen: set[str] = set()
        pos_rows = []
        for p in positions:
            if p["symbol"] in seen:
                continue
            seen.add(p["symbol"])
            pos_rows.append(p)
        alerts = db.fetchall(
            "SELECT symbol, family, direction, score, as_of FROM signal_alerts "
            "ORDER BY id DESC LIMIT 12"
        )
        universe = db.fetchall(
            "SELECT member_count, as_of_month, stage FROM universe_snapshots "
            "ORDER BY as_of_month DESC LIMIT 1"
        )
    finally:
        db.close()

    u_line = (
        f"{universe[0]['stage']} · {universe[0]['member_count']} names · {universe[0]['as_of_month']}"
        if universe
        else "not built — run sentinel universe rebuild"
    )
    fresh_html = "".join(
        f'<span><span class="dot {f.status}"></span>{f.source} · {f.status}</span>'
        for f in freshness
    )
    if pos_rows:
        pos_html = "<table><thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Mkt</th></tr></thead><tbody>"
        for p in pos_rows:
            pos_html += (
                f"<tr><td>{p['symbol']}</td>"
                f"<td class='mono'>{p['quantity']}</td>"
                f"<td class='mono'>{p['average_price']}</td>"
                f"<td class='mono'>{p['market_value']}</td></tr>"
            )
        pos_html += "</tbody></table>"
    else:
        pos_html = "<p class='empty'>No positions snapshot yet. Schwab OAuth on Windows fills this.</p>"

    if alerts:
        plan_html = "<table><thead><tr><th>Symbol</th><th>Family</th><th>Dir</th><th>Score</th><th>As of</th></tr></thead><tbody>"
        for a in alerts:
            plan_html += (
                f"<tr><td>{a['symbol']}</td><td>{a['family']}</td>"
                f"<td>{a['direction']}</td><td class='mono'>{a['score']}</td>"
                f"<td class='mono'>{a['as_of']}</td></tr>"
            )
        plan_html += "</tbody></table>"
    else:
        plan_html = "<p class='empty'>No alerts yet. Run <span class='mono'>sentinel scan</span>.</p>"

    body = f"""
    <h1>Dashboard</h1>
    <p class="lede">Situational awareness — positions, scanner alerts, data freshness. Paper mode only.</p>
    <div class="metrics">
      <div><div class="metric-label">Equity</div><div class="metric-value">—</div></div>
      <div><div class="metric-label">Day P&amp;L</div><div class="metric-value">—</div></div>
      <div><div class="metric-label">Universe</div><div class="metric-value" style="font-size:1rem">{u_line}</div></div>
      <div><div class="metric-label">trading_enabled</div><div class="metric-value" style="font-size:1rem">{"ON" if settings.trading_enabled else "OFF"}</div></div>
    </div>
    <section>
      <h2>Scanner alerts</h2>
      {plan_html}
    </section>
    <section>
      <h2>Positions</h2>
      {pos_html}
    </section>
    <section>
      <h2>Freshness</h2>
      <div class="freshness">{fresh_html}</div>
    </section>
    """
    return _shell("Dashboard", body, halt_open=killswitch.get_state() == killswitch.KillState.HALT)


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
    <p class="lede">Ops: heartbeat host, Schwab auth, freshness, kill state.</p>
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
    <p class="lede">HALT is UI-stubbed to the in-process killswitch. FLATTEN stays Phase 2 (passkey + typed confirm).</p>
    <p>Current state: <strong class="mono">{state}</strong></p>
    <form method="post" action="/halt" style="display:flex;gap:0.75rem;flex-wrap:wrap;margin-top:1rem">
      <button class="btn btn-danger" type="submit" name="action" value="halt">Engage HALT</button>
      <button class="btn btn-ghost" type="submit" name="action" value="resume">Resume (local stub)</button>
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


@app.get("/api/freshness")
def api_freshness() -> list[dict[str, Any]]:
    db = _db()
    try:
        return [f.to_dict() for f in read_freshness(db)]
    finally:
        db.close()
