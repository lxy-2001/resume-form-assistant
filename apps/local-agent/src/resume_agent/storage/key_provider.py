"""Key provisioning through an allowlisted operating-system keyring."""

from __future__ import annotations

import base64
import binascii
import secrets
from typing import Any, Protocol, runtime_checkable

import keyring

from resume_agent.storage.errors import StorageUnavailableError

KEY_LENGTH = 32


class _KeyringBackend(Protocol):
    def get_password(self, service: str, username: str) -> str | None: ...
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def delete_password(self, service: str, username: str) -> None: ...


def _system_backend_types() -> tuple[type[Any], ...]:
    """Return concrete OS keyring classes available on this platform."""

    candidates: list[type[Any]] = []
    for module_name, class_name in (
        ("keyring.backends.Windows", "WinVaultKeyring"),
        ("keyring.backends.macOS", "Keyring"),
        ("keyring.backends.SecretService", "Keyring"),
    ):
        try:
            module = __import__(module_name, fromlist=[class_name])
            candidate = getattr(module, class_name)
        except (ImportError, AttributeError):
            continue
        if isinstance(candidate, type):
            candidates.append(candidate)
    return tuple(candidates)


DEFAULT_ALLOWED_BACKEND_TYPES = _system_backend_types()

KeyMaterial = bytes


@runtime_checkable
class KeyProvider(Protocol):
    """Retrieve/provision/destroy opaque key material; unavailable backends return None."""

    def get_key(self) -> KeyMaterial | None: ...
    def provision_key(self) -> KeyMaterial | None: ...
    def destroy_key(self) -> bool: ...


class KeyringKeyProvider:
    """Store one opaque encryption key in an explicitly trusted OS keyring.

    The backend is injected for tests and packaged deployments.  Backend matching
    is exact (rather than ``isinstance``) so a subclass cannot silently bypass an
    allowlist.  No file, environment-variable, or plaintext fallback is used.
    """

    def __init__(
        self,
        service_name: str,
        username: str,
        *,
        backend: _KeyringBackend | None = None,
        allowed_backend_types: tuple[type[Any], ...] | None = None,
    ) -> None:
        self.service_name = self._safe_identifier(service_name, "service_name")
        self.username = self._safe_identifier(username, "username")
        self.backend = backend if backend is not None else keyring.get_keyring()
        self.allowed_backend_types = (
            DEFAULT_ALLOWED_BACKEND_TYPES
            if allowed_backend_types is None
            else tuple(allowed_backend_types)
        )

    @staticmethod
    def _safe_identifier(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    def _checked_backend(self) -> _KeyringBackend:
        backend = self.backend
        if backend is None or type(backend) not in self.allowed_backend_types:
            raise StorageUnavailableError("trusted OS keyring backend unavailable")
        for name in ("get_password", "set_password", "delete_password"):
            if not callable(getattr(backend, name, None)):
                raise StorageUnavailableError("trusted OS keyring backend unavailable")
        return backend

    @staticmethod
    def _decode(raw: object) -> KeyMaterial:
        if not isinstance(raw, str) or not raw:
            raise StorageUnavailableError("stored key is unavailable or malformed")
        try:
            decoded = base64.b64decode(raw.encode("ascii"), validate=True)
        except (UnicodeEncodeError, ValueError, binascii.Error) as exc:
            raise StorageUnavailableError("stored key is unavailable or malformed") from exc
        if len(decoded) != KEY_LENGTH:
            raise StorageUnavailableError("stored key is unavailable or malformed")
        return decoded

    def _read_raw(self, backend: _KeyringBackend) -> str | None:
        try:
            raw = backend.get_password(self.service_name, self.username)
        except Exception as exc:  # keyring backends expose implementation-specific errors
            raise StorageUnavailableError("OS keyring is unavailable") from exc
        if raw is None:
            return None
        self._decode(raw)
        return raw

    def get_key(self) -> KeyMaterial | None:
        backend = self._checked_backend()
        raw = self._read_raw(backend)
        return None if raw is None else self._decode(raw)

    def provision_key(self) -> KeyMaterial | None:
        backend = self._checked_backend()
        raw = self._read_raw(backend)
        if raw is not None:
            return self._decode(raw)
        try:
            key = secrets.token_bytes(KEY_LENGTH)
        except Exception as exc:
            raise StorageUnavailableError("secure key generation is unavailable") from exc
        if not isinstance(key, bytes) or len(key) != KEY_LENGTH:
            raise StorageUnavailableError("secure key generation is unavailable")
        encoded = base64.b64encode(key).decode("ascii")
        try:
            backend.set_password(self.service_name, self.username, encoded)
        except Exception as exc:
            raise StorageUnavailableError("OS keyring is unavailable") from exc
        return key

    def destroy_key(self) -> bool:
        backend = self._checked_backend()
        raw = self._read_raw(backend)
        try:
            backend.delete_password(self.service_name, self.username)
        except Exception as exc:
            raise StorageUnavailableError("OS keyring is unavailable") from exc
        return raw is not None
