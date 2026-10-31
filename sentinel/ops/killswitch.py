"""Kill switch stub — HALT blocks new risk; FLATTEN requires passkey (Phase 2)."""

from __future__ import annotations

from enum import StrEnum


class KillState(StrEnum):
    RUN = "RUN"
    HALT = "HALT"
    FLATTEN_ARMED = "FLATTEN_ARMED"  # requires passkey + typed confirm before use


_STATE = KillState.RUN


def get_state() -> KillState:
    return _STATE


def halt(reason: str = "") -> KillState:
    global _STATE
    _STATE = KillState.HALT
    return _STATE


def resume() -> KillState:
    """Owner-only path later; Phase 0 allows local resume for tests."""
    global _STATE
    _STATE = KillState.RUN
    return _STATE


def reset_for_tests() -> None:
    global _STATE
    _STATE = KillState.RUN
