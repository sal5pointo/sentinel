"""Auth reminder dry tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sentinel.ops.auth_reminder import compute_reminders, sunday_nudge_due


def test_t_minus_48h_window() -> None:
    expires = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
    now = expires - timedelta(hours=48, minutes=-10)  # 10 min after fire
    events = compute_reminders(expires, now=now, t_minus_hours=(48, 12))
    kinds = {e.kind for e in events}
    assert "t_minus_48h" in kinds


def test_expired() -> None:
    expires = datetime(2026, 10, 1, tzinfo=UTC)
    now = datetime(2026, 10, 2, tzinfo=UTC)
    events = compute_reminders(expires, now=now)
    assert events[0].kind == "expired"
    assert "read-nothing" in events[0].message


def test_sunday_nudge() -> None:
    assert sunday_nudge_due(local_weekday=6) is True
    assert sunday_nudge_due(local_weekday=0) is False
