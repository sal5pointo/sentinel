"""OS keychain / env secret resolution. Never stores Schwab passwords."""

from __future__ import annotations

import os
from typing import Protocol

KEYRING_SERVICE = os.environ.get("SENTINEL_KEYRING_SERVICE", "sentinel")


class SecretBackend(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...


class EnvSecretBackend:
    """Fallback for CI / offline tests — reads SENTINEL_SECRET_<NAME>."""

    def get(self, name: str) -> str | None:
        env_key = f"SENTINEL_SECRET_{name.upper()}"
        return os.environ.get(env_key)

    def set(self, name: str, value: str) -> None:
        os.environ[f"SENTINEL_SECRET_{name.upper()}"] = value


class KeyringSecretBackend:
    def get(self, name: str) -> str | None:
        try:
            import keyring
            from keyring.errors import KeyringError
        except ImportError:
            return None
        try:
            return keyring.get_password(KEYRING_SERVICE, name)
        except KeyringError:
            # Headless CI / VMs often have no keyring backend.
            return None

    def set(self, name: str, value: str) -> None:
        try:
            import keyring
            from keyring.errors import KeyringError
        except ImportError as exc:
            raise RuntimeError("keyring package not installed") from exc
        try:
            keyring.set_password(KEYRING_SERVICE, name, value)
        except KeyringError as exc:
            raise RuntimeError(
                "No OS keyring backend available; use env SENTINEL_SECRET_* for CI"
            ) from exc


class ChainedSecretBackend:
    def __init__(self, backends: list[SecretBackend]) -> None:
        self._backends = backends

    def get(self, name: str) -> str | None:
        for b in self._backends:
            val = b.get(name)
            if val:
                return val
        return None

    def set(self, name: str, value: str) -> None:
        # Prefer keyring when available; always allow env for tests.
        self._backends[0].set(name, value)


def default_backend() -> SecretBackend:
    return ChainedSecretBackend([KeyringSecretBackend(), EnvSecretBackend()])


def resolve_ref(ref: str, backend: SecretBackend | None = None) -> str | None:
    """Resolve ``keychain:name`` or return literal if not a ref."""
    if not ref.startswith("keychain:"):
        return ref
    name = ref.removeprefix("keychain:")
    be = backend or default_backend()
    return be.get(name)
