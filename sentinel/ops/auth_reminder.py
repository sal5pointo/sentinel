"""Schwab refresh-token expiry reminders (T-48h / T-12h).

Never stores passwords. Reminds the owner to re-run `sentinel auth login`
(browser consent only).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class ReminderEvent:
    kind: str  # t_minus_48h | t_minus_12h | expired | sunday_nudge
    message: str
    refresh_expires_at: datetime
    fire_at: datetime


def compute_reminders(
    refresh_expires_at: datetime,
    *,
    now: datetime | None = None,
    t_minus_hours: Iterable[int] = (48, 12),
) -> list[ReminderEvent]:
    """Return reminder events that should fire at ``now`` (inclusive window of 1h)."""
    if refresh_expires_at.tzinfo is None:
        refresh_expires_at = refresh_expires_at.replace(tzinfo=UTC)
    now = now or datetime.now(tz=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    events: list[ReminderEvent] = []
    if now >= refresh_expires_at:
        events.append(
            ReminderEvent(
                kind="expired",
                message=(
                    "Schwab refresh token expired — core is read-nothing / trade-nothing. "
                    "Owner: run `sentinel auth login` (browser consent; never share password)."
                ),
                refresh_expires_at=refresh_expires_at,
                fire_at=now,
            )
        )
        return events

    for hours in t_minus_hours:
        fire_at = refresh_expires_at - timedelta(hours=hours)
        # Fire if we are within the hour window after the scheduled fire time.
        if fire_at <= now < fire_at + timedelta(hours=1):
            events.append(
                ReminderEvent(
                    kind=f"t_minus_{hours}h",
                    message=f"Re-auth Schwab — ~{hours}h left on refresh token (≈30 seconds).",
                    refresh_expires_at=refresh_expires_at,
                    fire_at=fire_at,
                )
            )
    return events


def sunday_nudge_due(now: datetime | None = None, local_weekday: int | None = None) -> bool:
    """True on Sunday (weekday=6). Scheduler should also pin owner-local evening."""
    now = now or datetime.now(tz=UTC)
    wd = local_weekday if local_weekday is not None else now.weekday()
    return wd == 6
