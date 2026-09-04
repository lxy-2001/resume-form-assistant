"""T015 tests for encrypted, atomic profile persistence."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    ProfileSnapshot,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
)
from resume_agent.storage.encrypted_json import EncryptedJsonProfileStore
from resume_agent.storage.errors import (
    StorageCorruptOrUnrecoverableError,
    StorageUnavailableError,
)

PROFILE_ID = "profile-synthetic-f001-001"


def _snapshot(value: str = "Synthetic Test Person", version: int = 1) -> ProfileSnapshot:
    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    return ProfileSnapshot(
        profile_id=PROFILE_ID,
        profile_version=version,
        is_empty=False,
        fields=[
            FieldValue(
                id="person.full_name",
                label="姓名",
                field_type=FieldType.TEXT,
                value=value,
                scope=Scope.GLOBAL,
                sensitivity=Sensitivity.NORMAL,
                requires_confirmation=False,
                confirmed=True,
                source=Source(kind=SourceKind.MANUAL),
                updated_at=timestamp,
            )
        ],
        records=[],
        field_definitions=[],
        created_at=timestamp,
        updated_at=timestamp,
    )


class _FailingWriter:
    def write_atomic(self, destination: Path, payload: bytes) -> None:
        del destination, payload
        raise OSError("synthetic injected replace failure")


class _NullKeyProvider:
    def get_key(self) -> None:
        return None

    def provision_key(self) -> None:
        return None

    def destroy_key(self) -> bool:
        return False


class _MalformedKeyProvider:
    def get_key(self) -> bytes:
        return b"too-short"

    def provision_key(self) -> bytes:
        return b"too-short"

    def destroy_key(self) -> bool:
        return False


class _ProvisioningOnlyKeyProvider:
    """Synthetic provider that would create a replacement key if called."""

    def __init__(self) -> None:
        self.provision_calls = 0

    def get_key(self) -> None:
        return None

    def provision_key(self) -> bytes:
        self.provision_calls += 1
        return b"n" * 32

    def destroy_key(self) -> bool:
        return False


def test_uninitialized_store_reads_none_and_delete_is_idempotent(
    tmp_path: Path, fake_key_provider: object
) -> None:
    path = tmp_path / "profile.enc.json"
    store = EncryptedJsonProfileStore(path, fake_key_provider)

    assert store.read() is None
    store.delete()
    assert path.exists() is False


def test_write_round_trip_uses_versioned_authenticated_envelope(
    tmp_path: Path,
    fake_key_provider: object,
) -> None:
    path = tmp_path / "profile.enc.json"
    store = EncryptedJsonProfileStore(path, fake_key_provider)
    snapshot = _snapshot()

    store.write(snapshot)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    assert payload["algorithm"] == "AES-256-GCM"
    assert isinstance(payload["nonce"], str)
    assert isinstance(payload["ciphertext"], str)
    assert store.read().to_dict() == snapshot.to_dict()  # type: ignore[union-attr]
    assert b"Synthetic Test Person" not in path.read_bytes()


def test_missing_or_malformed_key_fails_closed_without_creating_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "profile.enc.json"

    for provider in (_NullKeyProvider(), _MalformedKeyProvider()):
        store = EncryptedJsonProfileStore(path, provider)
        with pytest.raises(StorageUnavailableError):
            store.write(_snapshot())
        assert path.exists() is False


def test_existing_snapshot_with_missing_key_fails_closed_without_replacing_file(
    tmp_path: Path,
    fake_key_provider: object,
) -> None:
    path = tmp_path / "profile.enc.json"
    EncryptedJsonProfileStore(path, fake_key_provider).write(_snapshot())
    before = path.read_bytes()
    missing_key = _ProvisioningOnlyKeyProvider()

    with pytest.raises(StorageUnavailableError):
        EncryptedJsonProfileStore(path, missing_key).write(_snapshot("Replacement", version=2))

    assert path.read_bytes() == before
    assert missing_key.provision_calls == 0


def test_wrong_key_and_tampered_ciphertext_raise_recovery_error(
    tmp_path: Path, fake_key_provider: object
) -> None:
    path = tmp_path / "profile.enc.json"
    writer = EncryptedJsonProfileStore(path, fake_key_provider)
    writer.write(_snapshot())

    from conftest import FakeKeyProvider

    wrong_provider = FakeKeyProvider(key_material=b"w" * 32)
    wrong_provider.provision_key()
    with pytest.raises(StorageCorruptOrUnrecoverableError):
        EncryptedJsonProfileStore(path, wrong_provider).read()

    envelope = json.loads(path.read_text(encoding="utf-8"))
    ciphertext = base64.b64decode(envelope["ciphertext"])
    envelope["ciphertext"] = base64.b64encode(bytes([ciphertext[0] ^ 1]) + ciphertext[1:]).decode(
        "ascii"
    )
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(StorageCorruptOrUnrecoverableError):
        writer.read()


def test_existing_snapshot_survives_injected_atomic_write_failure(
    tmp_path: Path,
    fake_key_provider: object,
) -> None:
    path = tmp_path / "profile.enc.json"
    good_store = EncryptedJsonProfileStore(path, fake_key_provider)
    original = _snapshot(version=1)
    good_store.write(original)
    before = path.read_bytes()

    failing = EncryptedJsonProfileStore(path, fake_key_provider, atomic_writer=_FailingWriter())
    with pytest.raises(StorageCorruptOrUnrecoverableError):
        failing.write(_snapshot("Replacement", version=2))

    assert path.read_bytes() == before
    assert good_store.read().to_dict() == original.to_dict()  # type: ignore[union-attr]


def test_no_plaintext_is_left_in_main_temp_or_backup_artifacts(
    tmp_path: Path,
    fake_key_provider: object,
) -> None:
    path = tmp_path / "profile.enc.json"
    EncryptedJsonProfileStore(path, fake_key_provider).write(_snapshot())

    for artifact in tmp_path.rglob("*"):
        if artifact.is_file():
            assert b"Synthetic Test Person" not in artifact.read_bytes()
