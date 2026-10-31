"""LLM queue package boundary stub."""

from __future__ import annotations

from pathlib import Path

from sentinel.llm.queue import LLMQueue
from sentinel.storage.db import Database


def test_enqueue(tmp_db: Path, tmp_path: Path) -> None:
    db = Database(tmp_db)
    q = LLMQueue(db=db, fs_path=tmp_path / "queue")
    msg = q.enqueue("memo_request", {"plan_id": "x", "symbol": "AAPL", "numbers": {}, "evidence": []})
    assert msg.status == "pending"
    pending = q.pending()
    assert len(pending) == 1
    assert list((tmp_path / "queue").glob("*.json"))
    db.close()
