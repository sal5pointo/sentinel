"""FastAPI health stub — read-only."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sentinel.reports.dashboard.app import app


def test_health(config_dir: object) -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["trading_enabled"] is False
    assert body["read_only"] is True


def test_index(config_dir: object) -> None:
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SENTINEL" in resp.text
