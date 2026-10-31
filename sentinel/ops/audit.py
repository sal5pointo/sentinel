"""Append-only audit log (SQLite + JSONL)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sentinel.storage.db import Database


class AuditLog:
    def __init__(
        self,
        db: Database | None = None,
        jsonl_path: str | Path = "logs/audit.jsonl",
    ) -> None:
        self.db = db
        self.jsonl_path = Path(jsonl_path)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        category: str,
        action: str,
        detail: dict[str, Any] | None = None,
        *,
        actor: str = "system",
    ) -> None:
        ts = datetime.now(tz=UTC).isoformat()
        payload = detail or {}
        line = {
            "ts": ts,
            "category": category,
            "action": action,
            "detail": payload,
            "actor": actor,
        }
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, default=str) + "\n")
        if self.db is not None:
            self.db.execute(
                "INSERT INTO audit_events(ts, category, action, detail_json, actor) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, category, action, json.dumps(payload, default=str), actor),
            )
