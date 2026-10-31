"""Config loading + TRADING_ENABLED hard gate."""

from __future__ import annotations

import pytest
from sentinel.config import (
    assert_trading_disabled,
    load_risk,
    load_settings,
    load_signals,
    load_universe,
    resolve_trading_enabled,
)


def test_settings_trading_disabled_by_default(config_dir: object) -> None:
    settings = load_settings()
    assert settings.trading_enabled is False
    assert resolve_trading_enabled() is False


def test_env_true_alone_does_not_enable(config_dir: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_ENABLED", "true")
    # YAML still false → must remain false
    assert resolve_trading_enabled() is False


def test_assert_trading_disabled_ok(config_dir: object) -> None:
    assert_trading_disabled()


def test_yaml_skeletons_load(config_dir: object) -> None:
    risk = load_risk()
    signals = load_signals()
    universe = load_universe()
    assert risk["use_margin_borrowing"] is False
    assert "high_low" in signals["enabled_families"]
    assert universe["stage"] == "U0"
    assert signals["congress"]["enabled"] is False
