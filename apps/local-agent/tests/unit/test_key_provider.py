"""T020 red tests for the OS-keyring-backed key provider.

All keyring calls use the injected in-memory backends below.  The suite must
never initialize or mutate the developer's real credential store.
"""

from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from resume_agent.storage.errors import StorageUnavailableError
from resume_agent.storage.key_provider import KeyringKeyProvider

SERVICE = "resume-agent.test"
USERNAME = "profile-main"
KEY = bytes(range(32))


@dataclass
class _MemoryBackend:
    """Minimal keyring backend fake; it never writes to the filesystem."""

    passwords: dict[tuple[str, str], str] = field(default_factory=dict)
    get_calls: int = 0
    set_calls: int = 0
    delete_calls: int = 0

    def get_password(self, service: str, username: str) -> str | None:
        self.get_calls += 1
        return self.passwords.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.set_calls += 1
        self.passwords[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.delete_calls += 1
        self.passwords.pop((service, username), None)


class _UntrustedBackend(_MemoryBackend):
    """Backend intentionally omitted from the provider allowlist."""


class _UnavailableBackend:
    def get_password(self, service: str, username: str) -> None:
        del service, username
        raise RuntimeError("synthetic keyring unavailable")

    def set_password(self, service: str, username: str, password: str) -> None:
        del service, username, password
        raise RuntimeError("synthetic keyring unavailable")

    def delete_password(self, service: str, username: str) -> None:
        del service, username
        raise RuntimeError("synthetic keyring unavailable")


def _provider(backend: Any, **kwargs: Any) -> KeyringKeyProvider:
    """Construct the provider with an explicit test allowlist and backend."""

    return KeyringKeyProvider(
        service_name=SERVICE,
        username=USERNAME,
        backend=backend,
        allowed_backend_types=(_MemoryBackend,),
        **kwargs,
    )


def test_allowlisted_backend_provisions_and_reuses_a_32_byte_key() -> None:
    backend = _MemoryBackend()
    provider = _provider(backend)

    assert provider.get_key() is None
    first = provider.provision_key()
    second = provider.provision_key()

    assert isinstance(first, bytes)
    assert len(first) == 32
    assert second == first
    assert backend.set_calls == 1
    assert backend.get_calls >= 3
    # The keyring value is encoded, not a raw Python repr or profile plaintext.
    stored = backend.passwords[(SERVICE, USERNAME)]
    assert stored != first.decode("latin1", errors="ignore")
    assert base64.b64decode(stored.encode("ascii")) == first


def test_existing_key_is_reused_without_reprovisioning() -> None:
    backend = _MemoryBackend(passwords={(SERVICE, USERNAME): base64.b64encode(KEY).decode("ascii")})
    provider = _provider(backend)

    assert provider.get_key() == KEY
    assert provider.provision_key() == KEY
    assert backend.set_calls == 0


def test_null_backend_fails_closed_without_fallback(tmp_path: Path) -> None:
    provider = _provider(None)

    with pytest.raises(StorageUnavailableError):
        provider.get_key()
    with pytest.raises(StorageUnavailableError):
        provider.provision_key()
    with pytest.raises(StorageUnavailableError):
        provider.destroy_key()
    assert list(tmp_path.rglob("*")) == []


def test_unavailable_backend_fails_closed_without_writing_anything() -> None:
    provider = _provider(_UnavailableBackend())

    with pytest.raises(StorageUnavailableError):
        provider.get_key()
    with pytest.raises(StorageUnavailableError):
        provider.provision_key()
    with pytest.raises(StorageUnavailableError):
        provider.destroy_key()


def test_untrusted_backend_is_rejected_before_keyring_calls() -> None:
    backend = _UntrustedBackend()
    provider = _provider(backend)

    with pytest.raises(StorageUnavailableError):
        provider.get_key()
    with pytest.raises(StorageUnavailableError):
        provider.provision_key()
    with pytest.raises(StorageUnavailableError):
        provider.destroy_key()
    assert backend.get_calls == 0
    assert backend.set_calls == 0
    assert backend.delete_calls == 0


@pytest.mark.parametrize(
    "stored",
    ["", "too-short", base64.b64encode(b"x" * 31).decode("ascii"), "not-base64!!!"],
)
def test_existing_null_malformed_or_wrong_length_key_fails_closed(stored: str) -> None:
    backend = _MemoryBackend(passwords={(SERVICE, USERNAME): stored})
    provider = _provider(backend)

    with pytest.raises(StorageUnavailableError):
        provider.get_key()
    # A malformed existing reference must never be replaced by a new key.
    assert backend.set_calls == 0


@pytest.mark.parametrize("bad_generated", [None, b"short", "not-bytes"])
def test_generated_key_type_and_length_are_validated(
    monkeypatch: pytest.MonkeyPatch, bad_generated: object
) -> None:
    backend = _MemoryBackend()
    provider = _provider(backend)
    monkeypatch.setattr(secrets, "token_bytes", lambda n: bad_generated)

    with pytest.raises(StorageUnavailableError):
        provider.provision_key()
    assert backend.set_calls == 0


def test_destroy_removes_only_the_keyring_reference_and_is_idempotent() -> None:
    backend = _MemoryBackend(passwords={(SERVICE, USERNAME): base64.b64encode(KEY).decode("ascii")})
    provider = _provider(backend)

    assert provider.destroy_key() is True
    assert provider.get_key() is None
    assert provider.destroy_key() is False
    assert backend.delete_calls == 1


def test_destroy_missing_reference_is_completed_without_delete_call() -> None:
    class _MissingDeleteRaisesBackend(_MemoryBackend):
        def delete_password(self, service: str, username: str) -> None:
            del service, username
            raise RuntimeError("delete of missing credential")

    backend = _MissingDeleteRaisesBackend()
    provider = KeyringKeyProvider(
        service_name=SERVICE,
        username=USERNAME,
        backend=backend,
        allowed_backend_types=(_MissingDeleteRaisesBackend,),
    )

    assert provider.destroy_key() is False
    assert backend.delete_calls == 0


def test_destroy_failure_is_reported_without_plaintext_fallback() -> None:
    class _DeleteFailureBackend(_MemoryBackend):
        def delete_password(self, service: str, username: str) -> None:
            del service, username
            raise RuntimeError("synthetic delete failure")

    backend = _DeleteFailureBackend(
        passwords={(SERVICE, USERNAME): base64.b64encode(KEY).decode("ascii")}
    )
    provider = _provider(backend)

    with pytest.raises(StorageUnavailableError):
        provider.destroy_key()
    assert backend.passwords[(SERVICE, USERNAME)]
