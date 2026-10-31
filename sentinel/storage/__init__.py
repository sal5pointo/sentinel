"""SQLite WAL storage scaffolding."""

from sentinel.storage.db import Database, connect, default_db_path

__all__ = ["Database", "connect", "default_db_path"]
