"""T016 contract tests for the local profile lifecycle API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    ProfileRecordType,
    ProfileSnapshot,
    RepeatableRecord,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
)
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore

ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"
PROFILE_ID = "profile-synthetic-f001-001"


class _ShapeValidator:
    def __init__(self, definition: str) -> None:
        self.definition = definition
        master = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        assert definition in master["$defs"]
        root = {
            "$schema": master["$schema"],
            "$id": master["$id"],
            "$defs": master["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
        Draft202012Validator.check_schema(root)
        self.validator = Draft202012Validator(root, format_checker=FormatChecker())

    def validate(self, payload: dict[str, object]) -> None:
        """Validate the complete payload against the authoritative schema."""
        self.validator.validate(payload)


def _validator(definition: str) -> _ShapeValidator:
    return _ShapeValidator(definition)


def _field(value: str = "Synthetic Test Person") -> FieldValue:
    return FieldValue(
        id="person.full_name",
        label="姓名",
        field_type=FieldType.TEXT,
        value=value,
        scope=Scope.GLOBAL,
        sensitivity=Sensitivity.NORMAL,
        requires_confirmation=False,
        confirmed=True,
        source=Source(kind=SourceKind.MANUAL),
        updated_at=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _empty_snapshot() -> ProfileSnapshot:
    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    return ProfileSnapshot(
        profile_id=PROFILE_ID,
        profile_version=0,
        is_empty=True,
        fields=[],
        records=[],
        field_definitions=[],
        created_at=timestamp,
        updated_at=timestamp,
    )


def _client(tmp_path: Path, service: ProfileService) -> TestClient:
    app = create_app(AppConfig(tmp_path), profile_service=service)
    return TestClient(app, client=("127.0.0.1", 1234), raise_server_exceptions=False)


def _envelope(operation: str) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "request_id": "req-synthetic-profile-001",
        "task_id": "task-synthetic-profile-001",
        "operation": operation,
    }


def test_profile_read_success_matches_master_contract(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    response = _client(tmp_path, service).post(
        "/v0/profile/read",
        json={**_envelope("profile.read"), "profile_id": PROFILE_ID},
    )

    assert response.status_code == 200
    payload = response.json()
    _validator("ProfileReadResponse").validate(payload)
    assert payload["operation"] == "profile.read.result"
    assert payload["profile"]["is_empty"] is True


def test_profile_upsert_success_matches_master_contract(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    body = {
        **_envelope("profile.upsert"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [_field().to_dict()],
    }

    response = _client(tmp_path, service).post("/v0/profile/upsert", json=body)

    assert response.status_code == 200
    payload = response.json()
    _validator("ProfileUpsertResponse").validate(payload)
    assert payload["written_field_ids"] == ["person.full_name"]
    assert payload["profile_version"] == 1


def test_upsert_delete_field_reports_record_removed_by_emptying_it(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert_record(
        PROFILE_ID,
        expected_profile_version=0,
        record=RepeatableRecord(
            record_id="education-route-delete-001",
            record_type=ProfileRecordType.EDUCATION,
            position=0,
            fields=[
                FieldValue(
                    id="education.school_name",
                    label="院校",
                    field_type=FieldType.TEXT,
                    value="Synthetic University",
                    scope=Scope.GLOBAL,
                    sensitivity=Sensitivity.NORMAL,
                    requires_confirmation=False,
                    confirmed=True,
                    source=Source(kind=SourceKind.MANUAL),
                    updated_at=datetime(2099, 1, 1, tzinfo=UTC),
                )
            ],
            confirmed=True,
            created_at=datetime(2099, 1, 1, tzinfo=UTC),
            updated_at=datetime(2099, 1, 1, tzinfo=UTC),
        ),
        user_confirmed=True,
    )
    client = _client(tmp_path, service)
    body = {
        **_envelope("profile.upsert"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 1,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [],
        "delete_field_ids": ["education.school_name"],
    }

    response = client.post("/v0/profile/upsert", json=body)

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted_field_ids"] == ["education.school_name"]
    assert payload["deleted_record_ids"] == ["education-route-delete-001"]


def test_partial_delete_retry_replays_without_running_cleanup_twice(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(PROFILE_ID, expected_profile_version=0, fields=[_field()], user_confirmed=True)
    calls = 0

    def failing_delete() -> None:
        nonlocal calls
        calls += 1
        raise OSError("synthetic delete failure")

    fake_profile_store.delete = failing_delete  # type: ignore[method-assign]
    client = _client(tmp_path, service)
    body = {
        **_envelope("profile.delete"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 1,
        "user_confirmed": True,
        "selection": {"delete_all": True},
    }

    first = client.post("/v0/profile/delete", json=body)
    second = client.post("/v0/profile/delete", json=body)

    assert first.status_code == 200
    assert first.json()["task_state"] == "partial"
    assert second.json() == first.json()
    assert calls == 1


def test_retried_upsert_replays_success_without_writing_twice(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    body = {
        **_envelope("profile.upsert"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [_field().to_dict()],
    }
    client = _client(tmp_path, service)

    first = client.post("/v0/profile/upsert", json=body)
    second = client.post("/v0/profile/upsert", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert fake_profile_store.write_calls == 1


def test_request_id_reuse_with_different_payload_is_rejected_without_mutation(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    client = _client(tmp_path, service)
    base = {
        **_envelope("profile.upsert"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [_field().to_dict()],
    }
    assert client.post("/v0/profile/upsert", json=base).status_code == 200
    changed = {**base, "fields": [_field("Different Synthetic Person").to_dict()]}

    response = client.post("/v0/profile/upsert", json=changed)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 1


@pytest.mark.parametrize(
    ("body", "expected_status"),
    [
        ({"operation": "profile.read", "profile_id": PROFILE_ID}, 400),
        (
            {
                **_envelope("profile.upsert"),
                "profile_id": PROFILE_ID,
                "expected_profile_version": 0,
                "user_confirmed": False,
                "fields": [_field().to_dict()],
            },
            400,
        ),
        ({**_envelope("unknown"), "profile_id": PROFILE_ID}, 400),
    ],
)
def test_malformed_or_unconfirmed_requests_return_redacted_errors(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
    body: dict[str, object],
    expected_status: int,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    response = _client(tmp_path, service).post("/v0/profile/read", json=body)

    assert response.status_code == expected_status
    payload = response.json()
    _validator("ErrorResponse").validate(payload)
    assert "Synthetic Test Person" not in response.text


def test_stale_upsert_returns_structured_error_without_body_echo(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(PROFILE_ID, expected_profile_version=0, fields=[_field()], user_confirmed=True)
    body = {
        **_envelope("profile.upsert"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "fields": [_field("Stale Synthetic Value").to_dict()],
    }

    response = _client(tmp_path, service).post("/v0/profile/upsert", json=body)

    assert response.status_code == 409
    _validator("ErrorResponse").validate(response.json())
    assert "Stale Synthetic Value" not in response.text


def test_upsert_rejects_unknown_nested_field_members_without_mutation(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    body = {
        **_envelope("profile.upsert"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [{**_field().to_dict(), "unexpected": "ignored-before"}],
    }

    response = _client(tmp_path, service).post("/v0/profile/upsert", json=body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 0


@pytest.mark.parametrize(
    "invalid_field",
    [
        {"id": "person.full_name", "value": "Compact"},
        {"field_id": "person.full_name", "value": "Legacy alias"},
    ],
)
def test_upsert_rejects_compact_or_legacy_field_shapes_without_mutation(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
    invalid_field: dict[str, object],
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    body = {
        **_envelope("profile.upsert"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [invalid_field],
    }

    response = _client(tmp_path, service).post("/v0/profile/upsert", json=body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 0
