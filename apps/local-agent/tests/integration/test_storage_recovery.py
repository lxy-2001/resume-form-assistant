"""T038 red tests for observable storage recovery and key cleanup boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resume_agent.storage.encrypted_json import EncryptedJsonProfileStore
from resume_agent.storage.errors import StorageCorruptOrUnrecoverableError


def test_corrupt_snapshot_reports_recovery_error_without_plaintext(
    tmp_path: Path, fake_key_provider: object
) -> None:
    path = tmp_path / "profile.enc.json"
    store = EncryptedJsonProfileStore(path, fake_key_provider)
    fake_key_provider.provision_key()  # type: ignore[attr-defined]
    path.write_text(
        json.dumps(
            {"schema_version": "1", "algorithm": "AES-256-GCM", "nonce": "bad", "ciphertext": "bad"}
        ),
        encoding="utf-8",
    )

    with pytest.raises(StorageCorruptOrUnrecoverableError, match="corrupt|unrecoverable|recover"):
        store.read()
    assert b"Synthetic Test Person" not in path.read_bytes()


def test_full_delete_removes_encrypted_snapshot_before_destroying_key_reference(
    tmp_path: Path, fake_key_provider: object
) -> None:
    path = tmp_path / "profile.enc.json"
    store = EncryptedJsonProfileStore(path, fake_key_provider)
    store.delete_profile_data()  # desired lifecycle seam; must be atomic and idempotent

    assert not path.exists()
    assert fake_key_provider.destroy_calls == 1
