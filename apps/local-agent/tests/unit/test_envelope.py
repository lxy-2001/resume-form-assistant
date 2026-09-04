"""T021 red tests for the versioned authenticated profile envelope."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any

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
from resume_agent.storage.encrypted_json import decode_envelope, encode_envelope
from resume_agent.storage.errors import StorageCorruptOrUnrecoverableError

KEY = bytes(range(32))
AAD = b"resume-agent/profile/v1"


def _snapshot(value: str = "Synthetic Test Person") -> ProfileSnapshot:
    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    return ProfileSnapshot(
        profile_id="profile-synthetic-f001-001",
        profile_version=1,
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


def _payload(snapshot: ProfileSnapshot | None = None) -> dict[str, Any]:
    return encode_envelope(snapshot or _snapshot(), KEY, aad=AAD)


def test_encode_decode_round_trip_has_versioned_aes_gcm_metadata() -> None:
    payload = _payload()

    assert payload["schema_version"] == "1"
    assert payload["algorithm"] == "AES-256-GCM"
    assert isinstance(payload["nonce"], str)
    assert isinstance(payload["ciphertext"], str)
    assert decode_envelope(payload, KEY, aad=AAD).to_dict() == _snapshot().to_dict()


def test_envelope_ciphertext_is_not_plaintext() -> None:
    payload = _payload()
    assert b"Synthetic Test Person" not in json.dumps(payload).encode("utf-8")


def test_wrong_key_tamper_and_aad_mismatch_fail_closed() -> None:
    payload = _payload()

    with pytest.raises(StorageCorruptOrUnrecoverableError):
        decode_envelope(payload, b"w" * 32, aad=AAD)
    with pytest.raises(StorageCorruptOrUnrecoverableError):
        decode_envelope(payload, KEY, aad=b"different-aad")

    tampered = dict(payload)
    ciphertext = base64.b64decode(str(payload["ciphertext"]))
    tampered["ciphertext"] = base64.b64encode(bytes([ciphertext[0] ^ 1]) + ciphertext[1:]).decode(
        "ascii"
    )
    with pytest.raises(StorageCorruptOrUnrecoverableError):
        decode_envelope(tampered, KEY, aad=AAD)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda data: data.update(schema_version="2"),
        lambda data: data.update(algorithm="AES-128-GCM"),
        lambda data: data.pop("nonce"),
        lambda data: data.update(nonce="not-base64!!!"),
        lambda data: data.update(ciphertext="not-base64!!!"),
    ],
)
def test_unknown_version_algorithm_or_malformed_fields_are_rejected(mutator: Any) -> None:
    payload = _payload()
    mutator(payload)

    with pytest.raises(StorageCorruptOrUnrecoverableError):
        decode_envelope(payload, KEY, aad=AAD)


@pytest.mark.parametrize("key", [b"short", b"k" * 31, b"k" * 33, "not-bytes"])
def test_invalid_key_material_is_rejected_without_leaking_values(key: object) -> None:
    with pytest.raises(StorageCorruptOrUnrecoverableError) as caught:
        encode_envelope(_snapshot(), key, aad=AAD)  # type: ignore[arg-type]
    assert "short" not in str(caught.value)
    assert "not-bytes" not in str(caught.value)
