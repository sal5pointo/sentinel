"""SQLite connection helpers with WAL mode."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from sentinel.storage.migrations import apply_migrations


def default_db_path() -> Path:
    override = os.environ.get("SENTINEL_DB_PATH")
    if override:
        return Path(override)
    root = Path(__file__).resolve().parent.parent.parent
    path = root / "data" / "sentinel.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


class Database:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else default_db_path()
        self.conn = connect(self.path)
        apply_migrations(self.conn)

    def execute(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def fetchall(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params).fetchall())

    def close(self) -> None:
        self.conn.close()
