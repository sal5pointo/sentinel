"""Typer CLI: auth, universe, scan, freshness, dashboard."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from sentinel import __version__
from sentinel.cli import auth as auth_cmd
from sentinel.config import assert_trading_disabled, load_settings, resolve_trading_enabled
from sentinel.logging_setup import setup_logging
from sentinel.ops.audit import AuditLog
from sentinel.ops.freshness import mark_edgar_fixture_ok, read_freshness
from sentinel.reports.goal_math import compute_goal_math, render_goal_math_table
from sentinel.storage.db import Database

app = typer.Typer(
    name="sentinel",
    help="SENTINEL — personal Schwab trading engine (Phase 1). Live trading disabled.",
    no_args_is_help=True,
)
auth_app = typer.Typer(help="Schwab OAuth helpers (owner-only; no passwords).")
universe_app = typer.Typer(help="Universe U0 builder / PIT snapshots.")
app.add_typer(auth_app, name="auth")
app.add_typer(universe_app, name="universe")
console = Console()


@app.callback()
def _root(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    setup_logging("DEBUG" if verbose else "INFO")
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
    console.print(f"SQLite ready (WAL): {db.path} schema=v2")
    db.close()


@universe_app.command("rebuild")
def universe_rebuild(
    month: str | None = typer.Option(
        None, "--month", help="PIT month YYYY-MM (default: current)"
    ),
    source: str = typer.Option("fixture", "--source", help="fixture | nasdaqtrader"),
    json_out: bool = typer.Option(False, "--json", help="Print snapshot JSON"),
) -> None:
    """Rebuild U0 universe and store a monthly point-in-time snapshot.

    Offline/CI uses vendored Nasdaq Trader + metrics fixtures under
    data/fixtures/universe (mirrored in tests/fixtures/universe).
    """
    assert_trading_disabled()
    from sentinel.universe.build import build_universe, persist_snapshot, snapshot_to_dict

    snap = build_universe(as_of_month=month, source=source)
    db = Database()
    try:
        sid = persist_snapshot(db, snap)
        console.print(
            f"U0 snapshot id={sid} month={snap.as_of_month} "
            f"members={snap.member_count} source={snap.source}"
        )
        if json_out:
            console.print_json(data=snapshot_to_dict(snap))
        else:
            table = Table(title="U0 sample (top ADV)")
            table.add_column("Symbol")
            table.add_column("ADV USD", justify="right")
            table.add_column("Price", justify="right")
            for m in snap.members[:15]:
                table.add_row(m.symbol, f"{m.adv_usd:,.0f}", f"{m.price:.2f}")
            console.print(table)
    finally:
        db.close()


@app.command("scan")
def scan(
    persist: bool = typer.Option(True, "--persist/--no-persist"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run MVP scanners on fixtures (deterministic offline)."""
    assert_trading_disabled()
    from sentinel.signals import persist_alerts, run_all_scanners

    bundle = run_all_scanners()
    db = Database()
    try:
        if persist:
            n = persist_alerts(db, bundle)
            mark_edgar_fixture_ok(db)
            console.print(f"persisted {n} alerts; edgar freshness=ok")
        if json_out:
            console.print_json(data=bundle)
        else:
            console.print(f"high_low: {len(bundle['high_low'])}")
            console.print(f"insider: {len(bundle['insider'])}")
            console.print(f"catalysts: {len(bundle['catalysts'])}")
            console.print(f"regime risk_on: {bundle['regime'].get('risk_on')}")
            console.print(f"composite symbols: {len(bundle['composite'])}")
            for row in bundle["composite"][:10]:
                console.print(
                    f"  {row['symbol']}: score={row['weighted_score']} "
                    f"families={row['families_hit']} confluence={row['confluence_ok']}"
                )
    finally:
        db.close()


@app.command("freshness")
def freshness_cmd() -> None:
    """Show Schwab + EDGAR source freshness."""
    db = Database()
    try:
        rows = read_freshness(db)
        console.print_json(data=[r.to_dict() for r in rows])
    finally:
        db.close()


@app.command("dashboard")
def dashboard(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
) -> None:
    """Run read-only FastAPI dashboard (Phase 1 shell)."""
    assert_trading_disabled()
    import uvicorn

    from sentinel.reports.dashboard.app import app as fastapi_app

    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
