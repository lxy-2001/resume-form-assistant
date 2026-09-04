"""T039 red API tests for profile.delete and profile.export lifecycle routes."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.models import (
    CustomFieldDefinition,
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


def test_delete_route_removes_only_the_selected_scoped_value(
    tmp_path: Path, fake_profile_store: object
) -> None:
    from datetime import UTC, datetime

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    definition = CustomFieldDefinition(
        id="custom.route-scope",
        label="目标城市",
        field_type=FieldType.TEXT,
        default_sensitivity=Sensitivity.NORMAL,
        requires_confirmation=True,
        is_custom=True,
        allowed_scopes=[Scope.GLOBAL, Scope.WEBSITE],
        created_at=timestamp,
        updated_at=timestamp,
    )
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="北京",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    saved = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        field_id=definition.id,
        value="上海",
        scope=Scope.WEBSITE,
        scope_context="jobs.example.invalid",
        user_confirmed=True,
    )
    client = TestClient(
        create_app(AppConfig(tmp_path), profile_service=service), client=("127.0.0.1", 1234)
    )
    body = {
        **_body("profile.delete"),
        "expected_profile_version": saved.profile_version,
        "selection": {
            "field_values": [
                {
                    "id": definition.id,
                    "scope": "website",
                    "scope_context": "jobs.example.invalid",
                }
            ]
        },
    }

    response = client.post("/v0/profile/delete", json=body)

    assert response.status_code == 200
    assert response.json()["deleted_field_ids"] == [definition.id]
    remaining = service.read(PROFILE_ID).fields
    assert [(field.scope.value, field.scope_context, field.value) for field in remaining] == [
        ("global", None, "北京")
    ]


def test_export_route_success_includes_completed_task_state(
    tmp_path: Path, fake_profile_store: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(PROFILE_ID, expected_profile_version=0, fields=[_field()], user_confirmed=True)
    client = TestClient(
        create_app(AppConfig(tmp_path), profile_service=service), client=("127.0.0.1", 1234)
    )
    response = client.post(
        "/v0/profile/export",
        json={
            **_body("profile.export"),
            "selection": {"all_profile_data": True},
            "format": "json",
            "destination": {
                "kind": "local_file",
                "path": str(tmp_path / "export.json"),
                "overwrite_existing": False,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_state"] == "completed"
    assert payload["operation"] == "profile.export.result"


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
