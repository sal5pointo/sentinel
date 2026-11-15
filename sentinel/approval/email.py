"""Email notifier interface — Gmail API stub + fixture sink for offline tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class EmailMessage:
    to: str
    subject: str
    body_text: str
    body_html: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> dict[str, Any]: ...


class FixtureEmailSender:
    """Records messages in memory — default for offline / CI."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> dict[str, Any]:
        self.sent.append(message)
        return {"status": "fixture_ok", "id": f"fix-{len(self.sent)}"}


class GmailApiStub:
    """Placeholder for owner Gmail API wiring on Windows — no network in Phase 2 CI."""

    def __init__(self, *, configured: bool = False) -> None:
        self.configured = configured
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError(
                "Gmail API not configured. Set up OAuth on Windows or use FixtureEmailSender."
            )
        self.sent.append(message)
        return {"status": "gmail_stub_queued", "to": message.to}


_DEFAULT = FixtureEmailSender()


def get_email_sender(*, provider: str = "fixture") -> EmailSender:
    if provider in {"fixture", "test"}:
        return _DEFAULT
    if provider == "gmail_api":
        return GmailApiStub(configured=False)
    return _DEFAULT


def render_plan_email(
    *,
    plan_id: str,
    symbol: str,
    side: str,
    quantity: float,
    entry: float,
    stop: float,
    confirm_url: str,
) -> EmailMessage:
    subject = f"SENTINEL plan {side} {quantity:g} {symbol}"
    text = (
        f"Approve plan {plan_id}\n"
        f"{side} {quantity:g} {symbol} ref ${entry:.2f} stop ${stop:.2f}\n"
        f"Open (GET never executes): {confirm_url}\n"
        f"Decision support only — you approve every trade.\n"
    )
    return EmailMessage(to="owner@example.com", subject=subject, body_text=text)
