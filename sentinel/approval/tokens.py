"""Single-use HMAC plan tokens — GET never executes."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sentinel.storage.db import Database


def _secret() -> bytes:
    env = os.environ.get("SENTINEL_APPROVAL_HMAC_SECRET")
    if env:
        return env.encode("utf-8")
    # Dev default — owner should set secret on Windows host. Not a password.
    return b"sentinel-dev-approval-hmac-not-for-production"


@dataclass(frozen=True)
class IssuedToken:
    token_id: str
    raw_token: str
    plan_id: str
    expires_at: str


def _hash_token(raw: str) -> str:
    return hmac.new(_secret(), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_token(
    db: Database,
    plan_id: str,
    *,
    ttl_seconds: int = 86_400,
    action_hint: str = "approve",
) -> IssuedToken:
    token_id = secrets.token_hex(8)
    raw = secrets.token_urlsafe(32)
    now = datetime.now(tz=UTC)
    expires = now + timedelta(seconds=ttl_seconds)
    db.execute(
        """
        INSERT INTO approval_tokens(token_id, plan_id, token_hash, action_hint, created_at, expires_at, single_use)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (
            token_id,
            plan_id,
            _hash_token(raw),
            action_hint,
            now.isoformat(),
            expires.isoformat(),
        ),
    )
    # Wire format: token_id.raw
    return IssuedToken(
        token_id=token_id,
        raw_token=f"{token_id}.{raw}",
        plan_id=plan_id,
        expires_at=expires.isoformat(),
    )


@dataclass
class TokenValidation:
    ok: bool
    plan_id: str | None = None
    token_id: str | None = None
    reason: str | None = None
    row: dict[str, object] | None = None


def validate_token(db: Database, raw_token: str, *, consume: bool = False) -> TokenValidation:
    if not raw_token or "." not in raw_token:
        return TokenValidation(ok=False, reason="malformed")
    token_id, raw = raw_token.split(".", 1)
    rows = db.fetchall("SELECT * FROM approval_tokens WHERE token_id = ?", (token_id,))
    if not rows:
        return TokenValidation(ok=False, reason="unknown")
    row = rows[0]
    expected = str(row["token_hash"])
    got = _hash_token(raw)
    if not hmac.compare_digest(expected, got):
        return TokenValidation(ok=False, reason="bad_signature")
    if row["used_at"] is not None:
        return TokenValidation(ok=False, reason="replay", plan_id=str(row["plan_id"]), token_id=token_id)
    expires = datetime.fromisoformat(str(row["expires_at"]))
    if datetime.now(tz=UTC) > expires:
        return TokenValidation(ok=False, reason="expired", plan_id=str(row["plan_id"]), token_id=token_id)
    if consume:
        db.execute(
            "UPDATE approval_tokens SET used_at = ? WHERE token_id = ? AND used_at IS NULL",
            (datetime.now(tz=UTC).isoformat(), token_id),
        )
        # Ensure single-use: if already used by race, reject
        check = db.fetchall("SELECT used_at FROM approval_tokens WHERE token_id = ?", (token_id,))
        if not check or check[0]["used_at"] is None:
            return TokenValidation(ok=False, reason="consume_failed", plan_id=str(row["plan_id"]))
    return TokenValidation(
        ok=True,
        plan_id=str(row["plan_id"]),
        token_id=token_id,
        row=dict(row),
    )
