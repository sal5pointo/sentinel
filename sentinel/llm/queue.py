"""Local filesystem / SQLite queue between sentinel-core and sentinel-llm.

Package boundary (Phase 0): separate process entrypoint later; for now we
document and stub the queue so core never shares broker secrets with LLM code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sentinel.storage.db import Database


@dataclass
class QueueMessage:
    id: int | None
    schema_name: str
    request: dict[str, Any]
    status: str = "pending"


class LLMQueue:
    """Enqueue work for the LLM worker. Core writes; LLM reads/responds."""

    def __init__(self, db: Database | None = None, fs_path: str | Path | None = None) -> None:
        self.db = db
        self.fs_path = Path(fs_path) if fs_path else Path("data/llm_queue")
        self.fs_path.mkdir(parents=True, exist_ok=True)

    def enqueue(self, schema_name: str, request: dict[str, Any]) -> QueueMessage:
        ts = datetime.now(tz=UTC).isoformat()
        payload = json.dumps(request)
        msg_id: int | None = None
        if self.db is not None:
            cur = self.db.execute(
                "INSERT INTO llm_queue(created_at, status, request_json, schema_name) "
                "VALUES (?, 'pending', ?, ?)",
                (ts, payload, schema_name),
            )
            msg_id = int(cur.lastrowid)
        # Mirror to filesystem for process separation / debugging
        name = f"{ts.replace(':', '')}_{schema_name}_{msg_id or 'fs'}.json"
        (self.fs_path / name).write_text(
            json.dumps({"schema_name": schema_name, "request": request}, indent=2),
            encoding="utf-8",
        )
        return QueueMessage(id=msg_id, schema_name=schema_name, request=request)

    def pending(self) -> list[QueueMessage]:
        if self.db is None:
            return []
        rows = self.db.fetchall(
            "SELECT id, schema_name, request_json, status FROM llm_queue WHERE status='pending'"
        )
        out: list[QueueMessage] = []
        for r in rows:
            out.append(
                QueueMessage(
                    id=int(r["id"]),
                    schema_name=str(r["schema_name"]),
                    request=json.loads(r["request_json"]),
                    status=str(r["status"]),
                )
            )
        return out
