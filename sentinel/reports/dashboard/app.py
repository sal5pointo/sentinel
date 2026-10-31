"""Minimal FastAPI health + read-only dashboard stub.

Web shell expands later (approval/WebAuthn). No order endpoints here.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from sentinel import __version__
from sentinel.config import load_settings, resolve_trading_enabled

app = FastAPI(
    title="SENTINEL Dashboard",
    version=__version__,
    description="Read-only Phase 0 shell. No trading endpoints.",
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "trading_enabled": resolve_trading_enabled(),
        "read_only": True,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    settings = load_settings()
    trading = "ON" if settings.trading_enabled else "OFF (required for Phase 0)"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>SENTINEL</title>
  <style>
    :root {{ --bg:#0f1419; --fg:#e7ecf1; --muted:#8b9aab; --accent:#3d8bfd; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, sans-serif;
           background:radial-gradient(1200px 600px at 10% -10%, #1b2838, var(--bg));
           color:var(--fg); min-height:100vh; }}
    main {{ max-width:720px; margin:0 auto; padding:3rem 1.25rem; }}
    h1 {{ font-size:2rem; letter-spacing:0.04em; margin:0 0 0.5rem; }}
    p {{ color:var(--muted); line-height:1.5; }}
    .pill {{ display:inline-block; border:1px solid #2a3a4d; padding:0.25rem 0.6rem;
             border-radius:4px; font-size:0.85rem; color:var(--fg); }}
    a {{ color:var(--accent); }}
  </style>
</head>
<body>
  <main>
    <h1>SENTINEL</h1>
    <p>Phase 0 read-only dashboard stub. Positions, plans, and freshness land in later phases.</p>
    <p><span class="pill">trading_enabled: {trading}</span></p>
    <p><a href="/health">/health</a></p>
  </main>
</body>
</html>"""
