"""Load YAML config with trading_enabled hard-default false."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# Agents never flip this. Owner + passkey only (Phase 2+).
TRADING_ENABLED_ENV = "TRADING_ENABLED"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def config_dir() -> Path:
    override = os.environ.get("SENTINEL_CONFIG_DIR")
    if override:
        return Path(override)
    return _project_root() / "config"


def load_yaml(name: str) -> dict[str, Any]:
    path = config_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config {path} must be a mapping")
    return data


class Settings(BaseModel):
    trading_enabled: bool = False
    account_hash_ref: str = "keychain:schwab_account_hash"
    timezone_exchange: str = "America/New_York"
    owner_timezone: str = "America/Phoenix"
    email_to: str = "keychain:owner_email"
    email_provider: str = "gmail_api"
    push_provider: str = "ntfy"
    max_plan_emails_per_day: int = 5
    broker_wrapper: str = "schwab_py"
    schwab: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any] = Field(default_factory=dict)
    dashboard: dict[str, Any] = Field(default_factory=dict)
    logging: dict[str, Any] = Field(default_factory=dict)
    goal: dict[str, Any] = Field(default_factory=dict)
    auth_reminder: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)


def resolve_trading_enabled(settings_raw: dict[str, Any] | None = None) -> bool:
    """Return whether trading is enabled.

    Env TRADING_ENABLED may only *reinforce* false. Setting it true without
    YAML ``trading_enabled: true`` is ignored. Agents must never flip YAML.
    """
    raw = settings_raw if settings_raw is not None else load_yaml("settings.yaml")
    yaml_flag = bool(raw.get("trading_enabled", False))
    env_val = os.environ.get(TRADING_ENABLED_ENV, "false").strip().lower()
    env_flag = env_val in {"1", "true", "yes", "on"}
    # Both must agree for true; default path is always false.
    return yaml_flag and env_flag


def load_settings() -> Settings:
    raw = load_yaml("settings.yaml")
    # Force the resolved gate into the model (never trust a lone env flip).
    raw = {**raw, "trading_enabled": resolve_trading_enabled(raw)}
    return Settings.model_validate(raw)


def load_risk() -> dict[str, Any]:
    return load_yaml("risk.yaml")


def load_signals() -> dict[str, Any]:
    return load_yaml("signals.yaml")


def load_universe() -> dict[str, Any]:
    return load_yaml("universe.yaml")


def assert_trading_disabled() -> None:
    """Raise if trading appears enabled — Phase 0 must stay paper/read-only."""
    if resolve_trading_enabled():
        raise RuntimeError(
            "TRADING_ENABLED is true. Phase 0 foundations refuse to run with "
            "live trading. Owner must keep trading_enabled: false until Phase 4."
        )
