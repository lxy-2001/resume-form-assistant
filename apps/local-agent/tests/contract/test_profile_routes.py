"""T016 contract tests for the local profile lifecycle API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    ProfileSnapshot,
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

    def validate(self, payload: dict[str, object]) -> None:
        """Check required fields against the authoritative master schema definition."""
        master = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        assert self.definition in master["$defs"]
        required = {
            "ProfileReadResponse": {
                "schema_version",
                "request_id",
                "task_id",
                "operation",
                "task_state",
                "profile",
                "warnings",
            },
            "ProfileUpsertResponse": {
                "schema_version",
                "request_id",
                "task_id",
                "operation",
                "profile_id",
                "profile_version",
                "written_field_ids",
                "deleted_field_ids",
                "warnings",
            },
            "ErrorResponse": {"schema_version", "request_id", "task_id", "operation", "error"},
        }[self.definition]
        assert required <= payload.keys()


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
