"""OAuth login scaffolding — owner-only browser consent; never stores passwords.

Flow (Phase 0 scaffold):
1. Load App Key/Secret from OS keychain (refs in settings.yaml).
2. Build Schwab consent URL (schwab-py helper when credentials present).
3. Print / open the URL; listen on localhost callback (documented pattern).
4. Persist encrypted token blob via keyring — never log token contents.

Agents must never automate Schwab username/password entry.
"""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from rich.console import Console

from sentinel.config import load_settings
from sentinel.logging_setup import get_logger
from sentinel.ops.audit import AuditLog
from sentinel.secrets import resolve_ref

log = get_logger("cli.auth")
console = Console()

# Documented consent host pattern for schwab-py / Trader API Individual apps.
SCHWAB_AUTH_BASE = "https://api.schwabapi.com/v1/oauth/authorize"


@dataclass(frozen=True)
class AuthLoginPlan:
    consent_url: str
    callback_url: str
    missing_secrets: list[str]
    opened_browser: bool
    notes: str


def build_consent_url(client_id: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
    }
    return f"{SCHWAB_AUTH_BASE}?{urlencode(params)}"


def login(*, open_browser: bool = True, audit: AuditLog | None = None) -> AuthLoginPlan:
    """Scaffold owner OAuth login. Does not accept or store passwords."""
    settings = load_settings()
    schwab = settings.schwab or {}
    callback = str(schwab.get("callback_url") or "https://127.0.0.1:8182")
    api_key_ref = str(schwab.get("api_key_ref") or "keychain:schwab_api_key")
    secret_ref = str(schwab.get("app_secret_ref") or "keychain:schwab_app_secret")

    missing: list[str] = []
    api_key = resolve_ref(api_key_ref)
    app_secret = resolve_ref(secret_ref)
    if not api_key:
        missing.append(api_key_ref)
    if not app_secret:
        missing.append(secret_ref)

    if missing:
        consent = (
            f"{SCHWAB_AUTH_BASE}?client_id=<APP_KEY>&redirect_uri={callback}"
            "&response_type=code"
        )
        notes = (
            "Owner must create a Schwab Developer Portal app (Trader API – Individual), "
            "store App Key/Secret in the OS keychain, then re-run `sentinel auth login`. "
            "Never paste a Schwab account password into this CLI. "
            "TODO once secrets exist: use schwab.auth.easy_client / client_from_manual_flow "
            f"(schwab-py pin) to capture the callback on {callback}."
        )
        console.print("[yellow]Missing keychain secrets:[/yellow]", ", ".join(missing))
        console.print("Consent URL pattern:")
        console.print(consent)
        console.print(notes)
        if audit:
            audit.record("auth", "login_scaffold_missing_secrets", {"missing": missing})
        return AuthLoginPlan(
            consent_url=consent,
            callback_url=callback,
            missing_secrets=missing,
            opened_browser=False,
            notes=notes,
        )

    assert api_key is not None
    consent = build_consent_url(api_key, callback)
    opened = False
    if open_browser:
        try:
            opened = bool(webbrowser.open(consent))
        except Exception:  # noqa: BLE001 — offline / headless OK
            opened = False

    notes = (
        "Owner completes consent in the browser. CLI must never type the Schwab password. "
        "After callback: persist refresh token via keyring (chmod 600 file fallback). "
        "Refresh tokens expire ~7 days — see ops/auth_reminder.py."
    )
    console.print("[green]Open this consent URL (owner only):[/green]")
    console.print(consent)
    if not opened:
        console.print("[dim]Browser open skipped or failed — paste the URL manually.[/dim]")
    console.print(notes)
    if audit:
        audit.record("auth", "login_consent_url_issued", {"callback": callback})
    # Live token exchange intentionally not executed without owner-present callback.
    return AuthLoginPlan(
        consent_url=consent,
        callback_url=callback,
        missing_secrets=[],
        opened_browser=opened,
        notes=notes,
    )


def auth_status() -> dict[str, Any]:
    settings = load_settings()
    schwab = settings.schwab or {}
    api_key = resolve_ref(str(schwab.get("api_key_ref") or "keychain:schwab_api_key"))
    return {
        "trading_enabled": settings.trading_enabled,
        "api_key_present": bool(api_key),
        "callback_url": schwab.get("callback_url"),
        "note": "Token blob presence check TODO after first successful login",
    }
