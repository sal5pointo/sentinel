"""WebAuthn / passkey scaffolding.

Default is secure: assertions required; without a registered credential,
confirm fails. Dev/test bypass only when SENTINEL_INSECURE_WEBAUTHN_BYPASS=1
is set explicitly (never enable on the Windows money host).
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from typing import Any


def insecure_bypass_enabled() -> bool:
    return os.environ.get("SENTINEL_INSECURE_WEBAUTHN_BYPASS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass
class WebAuthnRegistry:
    """In-memory credential registry for Phase 2 scaffolding."""

    credentials: dict[str, dict[str, Any]] = field(default_factory=dict)
    challenges: dict[str, str] = field(default_factory=dict)

    def begin_registration(self, user_id: str = "owner") -> dict[str, Any]:
        challenge = secrets.token_urlsafe(32)
        self.challenges[f"reg:{user_id}"] = challenge
        return {
            "challenge": challenge,
            "rp": {"id": "localhost", "name": "SENTINEL"},
            "user": {"id": user_id, "name": "owner", "displayName": "Owner"},
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
            "authenticatorSelection": {"userVerification": "required"},
        }

    def finish_registration(self, user_id: str, credential_id: str, public_key_pem: str = "stub") -> None:
        self.credentials[user_id] = {
            "credential_id": credential_id,
            "public_key_pem": public_key_pem,
        }

    def begin_assertion(self, user_id: str = "owner") -> dict[str, Any]:
        challenge = secrets.token_urlsafe(32)
        self.challenges[f"assert:{user_id}"] = challenge
        cred = self.credentials.get(user_id)
        return {
            "challenge": challenge,
            "rpId": "localhost",
            "allowCredentials": (
                [{"type": "public-key", "id": cred["credential_id"]}] if cred else []
            ),
            "userVerification": "required",
        }

    def verify_assertion(
        self,
        *,
        user_id: str = "owner",
        credential_id: str | None,
        client_challenge: str | None,
        assertion_b64: str | None = None,
    ) -> tuple[bool, str]:
        """Verify passkey assertion. Returns (ok, reason)."""
        if insecure_bypass_enabled():
            return True, "insecure_bypass"

        cred = self.credentials.get(user_id)
        if not cred:
            return False, "no_registered_credential"
        expected = self.challenges.get(f"assert:{user_id}")
        if not expected or not client_challenge or client_challenge != expected:
            return False, "bad_challenge"
        if not credential_id or credential_id != cred["credential_id"]:
            return False, "bad_credential"
        if not assertion_b64:
            return False, "missing_assertion"
        # Full cryptographic verify lands with real WebAuthn lib + RP ID = tunnel host.
        # Scaffolding accepts a non-empty assertion that matches the challenge binding.
        if len(assertion_b64) < 8:
            return False, "assertion_too_short"
        self.challenges.pop(f"assert:{user_id}", None)
        return True, "ok"


REGISTRY = WebAuthnRegistry()
