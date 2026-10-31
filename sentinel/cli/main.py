"""Typer CLI: `sentinel auth login`, health, goal-math, dashboard."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from sentinel import __version__
from sentinel.cli import auth as auth_cmd
from sentinel.config import assert_trading_disabled, load_settings, resolve_trading_enabled
from sentinel.logging_setup import setup_logging
from sentinel.ops.audit import AuditLog
from sentinel.reports.goal_math import compute_goal_math, render_goal_math_table
from sentinel.storage.db import Database

app = typer.Typer(
    name="sentinel",
    help="SENTINEL — personal Schwab trading engine (Phase 0). Live trading disabled.",
    no_args_is_help=True,
)
auth_app = typer.Typer(help="Schwab OAuth helpers (owner-only; no passwords).")
app.add_typer(auth_app, name="auth")
console = Console()


@app.callback()
def _root(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    setup_logging("DEBUG" if verbose else "INFO")
    # Soft check — refuse accidental live mode in Phase 0 CLI paths that matter.
    ctx.ensure_object(dict)
    ctx.obj["trading_enabled"] = resolve_trading_enabled()


@app.command("version")
def version() -> None:
    console.print(__version__)


@app.command("status")
def status() -> None:
    settings = load_settings()
    console.print(f"version: {__version__}")
    console.print(f"trading_enabled: {settings.trading_enabled}")
    console.print(f"exchange_tz: {settings.timezone_exchange}")
    console.print(f"owner_tz: {settings.owner_timezone}")
    console.print(f"broker_wrapper: {settings.broker_wrapper}")


@auth_app.command("login")
def auth_login(
    no_browser: bool = typer.Option(False, "--no-browser", help="Print URL only"),
) -> None:
    """Open Schwab consent URL pattern. Owner completes login in browser."""
    assert_trading_disabled()
    db = Database()
    audit = AuditLog(db=db)
    plan = auth_cmd.login(open_browser=not no_browser, audit=audit)
    if plan.missing_secrets:
        raise typer.Exit(code=2)


@auth_app.command("status")
def auth_status_cmd() -> None:
    info = auth_cmd.auth_status()
    for k, v in info.items():
        console.print(f"{k}: {v}")


@app.command("goal-math")
def goal_math(
    equity: float = typer.Option(..., "--equity", help="Starting equity USD"),
    target: float = typer.Option(250_000.0, "--target", help="Target equity USD"),
) -> None:
    """Compute required return to hit the goal (sample or live equity)."""
    rows = compute_goal_math(equity, target_equity=target)
    console.print(render_goal_math_table(rows))


@app.command("init-db")
def init_db(
    path: Path | None = typer.Option(None, "--path", help="SQLite path"),
) -> None:
    db = Database(path)
    console.print(f"SQLite ready (WAL): {db.path}")
    db.close()


@app.command("dashboard")
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
) -> None:
    """Run read-only FastAPI health/dashboard stub."""
    assert_trading_disabled()
    import uvicorn

    from sentinel.reports.dashboard.app import app as fastapi_app

    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
