"""FastAPI Phase 1 dashboard — read-only + HALT stub."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sentinel.ops import killswitch
from sentinel.reports.dashboard.app import app


def test_health(config_dir: object) -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["trading_enabled"] is False
    assert body["read_only"] is True
    assert body["mode"] == "paper"


def test_index(config_dir: object, tmp_db: object) -> None:
    killswitch.reset_for_tests()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SENTINEL" in resp.text
    assert "Paper" in resp.text
    assert "HALT" in resp.text
    assert "Freshness" in resp.text


def test_halt_post(config_dir: object, tmp_db: object) -> None:
    killswitch.reset_for_tests()
    client = TestClient(app)
    resp = client.post("/halt", data={"action": "halt"}, follow_redirects=False)
    assert resp.status_code in {303, 302}
    assert killswitch.get_state() == killswitch.KillState.HALT
    page = client.get("/halt")
    assert "HALT" in page.text
    client.post("/halt", data={"action": "resume"}, follow_redirects=True)
    assert killswitch.get_state() == killswitch.KillState.RUN


def test_status_page(config_dir: object, tmp_db: object) -> None:
    client = TestClient(app)
    resp = client.get("/status")
    assert resp.status_code == 200
    assert "Freshness" in resp.text
