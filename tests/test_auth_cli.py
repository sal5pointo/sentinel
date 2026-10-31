"""Auth login scaffolding without credentials."""

from __future__ import annotations

from sentinel.cli.auth import build_consent_url, login


def test_build_consent_url() -> None:
    url = build_consent_url("APPKEY", "https://127.0.0.1:8182")
    assert "client_id=APPKEY" in url
    assert "response_type=code" in url


def test_login_missing_secrets(config_dir: object) -> None:
    plan = login(open_browser=False)
    assert plan.missing_secrets
    assert "oauth/authorize" in plan.consent_url
    assert "password" in plan.notes.lower() or "Never" in plan.notes
