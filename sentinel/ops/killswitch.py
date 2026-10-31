"""Kill switch — HALT blocks new risk; FLATTEN requires passkey (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentinel.storage.db import Database


class KillState(StrEnum):
    RUN = "RUN"
    HALT = "HALT"
    FLATTEN_ARMED = "FLATTEN_ARMED"  # requires passkey + typed confirm before use


_STATE = KillState.RUN
_REASON = ""


def get_state() -> KillState:
    return _STATE


def get_reason() -> str:
    return _REASON


def halt(reason: str = "") -> KillState:
    global _STATE, _REASON
    _STATE = KillState.HALT
    _REASON = reason
    return _STATE


def resume() -> KillState:
    """Owner-only path later; Phase 1 allows local resume for tests/UI stub."""
    global _STATE, _REASON
    _STATE = KillState.RUN
    _REASON = ""
    return _STATE


def reset_for_tests() -> None:
    global _STATE, _REASON
    _STATE = KillState.RUN
    _REASON = ""


def persist(db: Database) -> None:
    now = datetime.now(tz=UTC).isoformat()
    db.execute(
        "INSERT INTO kill_state(id, state, reason, updated_at) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET state=excluded.state, reason=excluded.reason, "
        "updated_at=excluded.updated_at",
        (_STATE.value, _REASON, now),
    )


def load_from_db(db: Database) -> KillState:
    global _STATE, _REASON
    rows = db.fetchall("SELECT state, reason FROM kill_state WHERE id = 1")
    if not rows:
        return _STATE
    _STATE = KillState(str(rows[0]["state"]))
    _REASON = str(rows[0]["reason"] or "")
    return _STATE
