"""T028 contract tests for US2 records and custom-field mutations.

These tests intentionally exercise the single ``profile.upsert`` boundary used
by F001.  The shared lifecycle envelope stays unchanged while US2 adds typed
record/definition mutation members to the request and corresponding ID-only
mutation metadata to the response.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-synthetic-f001-001"
TS = "2099-01-01T00:00:00Z"


def _client(tmp_path: Path, service: Any) -> TestClient:
    return TestClient(
        create_app(AppConfig(tmp_path), profile_service=service),
        client=("127.0.0.1", 1234),
        raise_server_exceptions=False,
    )


def _envelope(request_id: str, operation: str = "profile.upsert") -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "request_id": request_id,
        "task_id": f"task-{request_id}",
        "operation": operation,
    }


def _field(
    field_id: str,
    label: str,
    field_type: str,
    value: Any,
    *,
    is_custom: bool = False,
    options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    field: dict[str, Any] = {
        "id": field_id,
        "label": label,
        "field_type": field_type,
        "value": value,
        "scope": "global",
        "sensitivity": "normal",
        "requires_confirmation": is_custom,
        "confirmed": True,
        "source": {"kind": "manual"},
        "updated_at": TS,
        "is_custom": is_custom,
    }
    if options is not None:
        field["options"] = options
    return field


def _record(record_id: str, record_type: str, position: int) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "record_type": record_type,
        "position": position,
        "fields": [
            _field(
                "education.school_name"
                if record_type == "education"
                else "experience.organization",
                "院校/培养单位" if record_type == "education" else "公司/单位/组织",
                "text",
                "Synthetic University" if record_type == "education" else "Synthetic Labs",
            )
        ],
        "confirmed": True,
        "created_at": TS,
        "updated_at": TS,
    }


def _custom_definition(
    field_id: str = "custom.preferred_city",
    *,
    label: str = "可接受城市",
    options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": field_id,
        "label": label,
        "field_type": "enum",
        "default_sensitivity": "normal",
        "requires_confirmation": True,
        "is_custom": True,
        "allowed_scopes": ["global", "application"],
        "options": options
        or [
            {"value": "beijing", "label": "北京"},
            {"value": "shanghai", "label": "上海"},
        ],
        "created_at": TS,
        "updated_at": TS,
    }


def _upsert_body(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        **_envelope("req-us2-create"),
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [],
        "records": [],
        "custom_field_definitions": [],
    }
    body.update(changes)
    return body


def test_upsert_accepts_repeatable_records_and_custom_definition(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    """One confirmed request can add records and a typed custom definition."""

    from resume_agent.profile.service import ProfileService

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    record = _record("education-synthetic-001", "education", 0)
    custom_definition = _custom_definition()
    body = _upsert_body(
        fields=[
            _field(
                "custom.preferred_city",
                "可接受城市",
                "enum",
                "beijing",
                is_custom=True,
                options=custom_definition["options"],
            )
        ],
        records=[record],
        custom_field_definitions=[custom_definition],
    )

    response = _client(tmp_path, service).post("/v0/profile/upsert", json=body)

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation"] == "profile.upsert.result"
    assert payload["profile_version"] == 1
    assert payload["written_record_ids"] == [record["record_id"]]
    assert payload["written_custom_field_definition_ids"] == [custom_definition["id"]]
    # The mutation response is metadata-only and must not echo profile values.
    assert "beijing" not in response.text
    assert "Synthetic University" not in response.text


def test_upsert_supports_record_order_and_individual_deletion(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    """Ordering and deletion identify records explicitly, never by list index."""

    from resume_agent.profile.service import ProfileService

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    first = _record("education-synthetic-001", "education", 0)
    second = _record("education-synthetic-002", "education", 1)
    create_response = _client(tmp_path, service).post(
        "/v0/profile/upsert",
        json=_upsert_body(
            request_id="req-us2-records",
            records=[first, second],
        ),
    )
    assert create_response.status_code == 200

    mutation = _upsert_body(
        request_id="req-us2-reorder-delete",
        expected_profile_version=1,
        fields=[],
        records=[],
        record_order=[second["record_id"], first["record_id"]],
        delete_record_ids=[second["record_id"]],
    )
    response = _client(tmp_path, service).post("/v0/profile/upsert", json=mutation)

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_version"] == 2
    assert payload["deleted_record_ids"] == [second["record_id"]]
    assert payload["record_order"] == [first["record_id"]]


def test_custom_definition_collision_returns_structured_error_without_mutation(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    """A custom ID cannot shadow a standard definition."""

    from resume_agent.profile.service import ProfileService

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    body = _upsert_body(
        request_id="req-us2-collision",
        custom_field_definitions=[_custom_definition("person.full_name", label="冒充姓名字段")],
    )

    response = _client(tmp_path, service).post("/v0/profile/upsert", json=body)

    assert response.status_code in {400, 409}
    payload = response.json()
    assert payload["error"]["code"] == "CUSTOM_FIELD_CONFLICT"
    assert "冒充姓名字段" not in response.text
    assert fake_profile_store.write_calls == 0


def test_custom_enum_value_outside_options_is_rejected(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    """An enum value outside its definition's options cannot be persisted."""

    from resume_agent.profile.service import ProfileService

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    definition = _custom_definition()
    body = _upsert_body(
        request_id="req-us2-invalid-option",
        custom_field_definitions=[definition],
        fields=[
            _field(
                definition["id"],
                definition["label"],
                "enum",
                "guangzhou",
                is_custom=True,
                options=definition["options"],
            )
        ],
    )

    response = _client(tmp_path, service).post("/v0/profile/upsert", json=body)

    assert response.status_code in {400, 409}
    payload = response.json()
    assert payload["error"]["code"] == "INVALID_FIELD_VALUE"
    assert "guangzhou" not in response.text
    assert fake_profile_store.write_calls == 0


def test_us2_mutation_requires_confirmation_and_current_version(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    """Unconfirmed or stale record/definition mutations are rejected atomically."""

    from resume_agent.profile.service import ProfileService

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    record = _record("project-synthetic-001", "project", 0)
    base = _upsert_body(
        request_id="req-us2-base",
        records=[record],
    )
    assert _client(tmp_path, service).post("/v0/profile/upsert", json=base).status_code == 200

    unconfirmed = _upsert_body(
        request_id="req-us2-unconfirmed",
        expected_profile_version=1,
        user_confirmed=False,
        records=[record],
    )
    response = _client(tmp_path, service).post("/v0/profile/upsert", json=unconfirmed)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert fake_profile_store.write_calls == 1

    stale = _upsert_body(
        request_id="req-us2-stale",
        expected_profile_version=0,
        records=[record],
    )
    response = _client(tmp_path, service).post("/v0/profile/upsert", json=stale)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_PROFILE_VERSION"
    assert fake_profile_store.write_calls == 1
