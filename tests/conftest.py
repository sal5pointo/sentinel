"""Offline fixtures — no live Schwab credentials."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure trading stays off for the entire test suite.
os.environ["TRADING_ENABLED"] = "false"


@pytest.fixture()
def config_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    root = Path(__file__).resolve().parent.parent / "config"
    monkeypatch.setenv("SENTINEL_CONFIG_DIR", str(root))
    return root


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "test.db"
    monkeypatch.setenv("SENTINEL_DB_PATH", str(path))
    return path
