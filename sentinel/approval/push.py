"""Push notifier interface — ntfy stub + fixture sink."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class PushMessage:
    title: str
    body: str
    url: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class PushSender(Protocol):
    def send(self, message: PushMessage) -> dict[str, Any]: ...


class FixturePushSender:
    def __init__(self) -> None:
        self.sent: list[PushMessage] = []

    def send(self, message: PushMessage) -> dict[str, Any]:
        self.sent.append(message)
        return {"status": "fixture_ok", "id": f"push-{len(self.sent)}"}


class NtfyStub:
    """ntfy.sh / self-host stub — no network in CI."""

    def __init__(self, *, topic: str | None = None) -> None:
        self.topic = topic
        self.sent: list[PushMessage] = []

    def send(self, message: PushMessage) -> dict[str, Any]:
        if not self.topic:
            raise RuntimeError("ntfy topic not configured")
        self.sent.append(message)
        return {"status": "ntfy_stub_queued", "topic": self.topic}


_DEFAULT = FixturePushSender()


def get_push_sender(*, provider: str = "fixture") -> PushSender:
    if provider in {"fixture", "test"}:
        return _DEFAULT
    if provider == "ntfy":
        return NtfyStub(topic=None)
    return _DEFAULT
