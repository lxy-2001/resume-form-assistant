"""T039 red API tests for profile.delete and profile.export lifecycle routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
)
from resume_agent.profile.service import ProfileService

PROFILE_ID = "profile-synthetic-f001-001"


def _field() -> FieldValue:
    from datetime import UTC, datetime

    return FieldValue(
        id="person.full_name",
        label="姓名",
        field_type=FieldType.TEXT,
        value="Synthetic Person",
        scope=Scope.GLOBAL,
        sensitivity=Sensitivity.NORMAL,
        requires_confirmation=False,
        confirmed=True,
        source=Source(kind=SourceKind.MANUAL),
        updated_at=datetime(2099, 1, 1, tzinfo=UTC),
    )


def _body(operation: str) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "request_id": "req-lifecycle-synthetic",
        "task_id": "task-lifecycle-synthetic",
        "operation": operation,
        "profile_id": PROFILE_ID,
        "expected_profile_version": 1,
        "user_confirmed": True,
    }


def test_delete_route_returns_contract_shaped_result(
    tmp_path: Path, fake_profile_store: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(PROFILE_ID, expected_profile_version=0, fields=[_field()], user_confirmed=True)
    client = TestClient(
        create_app(AppConfig(tmp_path), profile_service=service), client=("127.0.0.1", 1234)
    )

    response = client.post(
        "/v0/profile/delete",
        json={**_body("profile.delete"), "selection": {"field_ids": ["person.full_name"]}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation"] == "profile.delete.result"
    assert payload["deleted_field_ids"] == ["person.full_name"]
    assert payload["cleanup_pending"] == []


def test_export_route_rejects_stale_version_and_remote_destination(
    tmp_path: Path, fake_profile_store: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    client = TestClient(
        create_app(AppConfig(tmp_path), profile_service=service), client=("127.0.0.1", 1234)
    )
    body = {
        **_body("profile.export"),
        "expected_profile_version": 0,
        "selection": {"all_profile_data": True},
        "format": "json",
        "destination": {
            "kind": "local_file",
            "path": "https://example.invalid/out.json",
            "overwrite_existing": False,
        },
    }

    response = client.post("/v0/profile/export", json=body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] in {
        "INVALID_PROFILE_SELECTION",
        "EXPORT_FAILED",
        "STALE_PROFILE_VERSION",
    }
    assert "https://example.invalid" not in response.text
