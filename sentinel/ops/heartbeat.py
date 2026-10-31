"""Dead-man heartbeat stub (e.g. healthchecks.io) — Phase 0 no network required."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from sentinel.logging_setup import get_logger

log = get_logger("ops.heartbeat")


@dataclass
class HeartbeatResult:
    ok: bool
    target: str | None
    skipped: bool
    detail: str


def ping(url: str | None = None) -> HeartbeatResult:
    """Ping dead-man URL if configured. Offline-safe: skips when unset."""
    target = url or os.environ.get("HEALTHCHECKS_URL")
    if not target:
        return HeartbeatResult(
            ok=True,
            target=None,
            skipped=True,
            detail="HEALTHCHECKS_URL unset — heartbeat skipped",
        )
    # Phase 0: do not force network in tests; log intent only unless explicitly called live.
    log.info("heartbeat would ping %s at %s", target, datetime.now(tz=UTC).isoformat())
    return HeartbeatResult(ok=True, target=target, skipped=False, detail="logged (live HTTP TODO)")
