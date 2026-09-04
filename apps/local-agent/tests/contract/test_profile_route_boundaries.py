"""Boundary tests for the shared profile.upsert HTTP envelope."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-synthetic-route-boundary"


def _client(tmp_path: Path, store: ProfileStore) -> TestClient:
    service = ProfileService(store, profile_id=PROFILE_ID)
    app = create_app(AppConfig(tmp_path), profile_service=service)
    return TestClient(app, client=("127.0.0.1", 1234), raise_server_exceptions=False)


def _body(**changes: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "0.1",
        "request_id": "req-route-boundary",
        "task_id": "task-route-boundary",
        "operation": "profile.upsert",
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [
            {
                "id": "person.full_name",
                "label": "姓名",
                "field_type": "text",
                "value": "Synthetic User",
                "scope": "global",
                "sensitivity": "normal",
                "requires_confirmation": False,
                "confirmed": True,
                "source": {"kind": "manual"},
                "updated_at": "2099-01-01T00:00:00Z",
            }
        ],
    }
    result.update(changes)
    return result


def test_upsert_rejects_non_mapping_mutation_members_without_500(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    response = _client(tmp_path, fake_profile_store).post(
        "/v0/profile/upsert", json=_body(records=["not-a-record"])
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"records": []},
        {"custom_field_definitions": []},
        {"delete_record_ids": []},
        {"delete_custom_field_definition_ids": []},
        {
            "fields": [
                {
                    "id": "person.full_name",
                    "label": "姓名",
                    "field_type": "text",
                    "value": "Synthetic User",
                    "scope": "global",
                    "scope_context": None,
                    "sensitivity": "normal",
                    "requires_confirmation": False,
                    "confirmed": True,
                    "source": {"kind": "manual"},
                    "updated_at": "2099-01-01T00:00:00Z",
                }
            ]
        },
    ],
)
def test_upsert_rejects_shapes_that_the_master_schema_rejects(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
    changes: dict[str, Any],
) -> None:
    response = _client(tmp_path, fake_profile_store).post(
        "/v0/profile/upsert", json=_body(**changes)
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 0


def test_upsert_rejects_non_boolean_option_flags_at_http_boundary(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    field = dict(_body()["fields"][0])
    field["options"] = [{"value": "x", "label": "X", "selected": "false"}]

    response = _client(tmp_path, fake_profile_store).post(
        "/v0/profile/upsert", json=_body(fields=[field])
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 0


@pytest.mark.parametrize(
    ("path", "changes"),
    [
        ("/v0/profile/upsert", {"operation": ["profile.upsert"]}),
        (
            "/v0/profile/upsert",
            {
                "fields": [
                    {
                        **_body()["fields"][0],
                        "scope": ["global"],
                    }
                ]
            },
        ),
        (
            "/v0/profile/upsert",
            {
                "fields": [
                    {
                        **_body()["fields"][0],
                        "source": {"kind": ["manual"]},
                    }
                ]
            },
        ),
        (
            "/v0/profile/upsert",
            {
                "fields": [
                    {
                        **_body()["fields"][0],
                        "validation": {"format": ["email"]},
                    }
                ]
            },
        ),
        (
            "/v0/profile/export",
            {
                "operation": "profile.export",
                "selection": {"scopes": [["global"]]},
                "format": "json",
                "destination": {
                    "kind": "local_file",
                    "path": "C:/synthetic-export.json",
                    "overwrite_existing": False,
                },
            },
        ),
    ],
)
def test_malformed_unhashable_members_return_structured_client_errors(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
    path: str,
    changes: dict[str, Any],
) -> None:
    body = _body(**changes)
    if path.endswith("/export"):
        body = {
            **body,
            "operation": "profile.export",
            "expected_profile_version": 0,
            "selection": changes["selection"],
            "format": "json",
            "destination": changes["destination"],
        }
    response = _client(tmp_path, fake_profile_store).post(path, json=body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 0


def test_upsert_rejects_invalid_or_duplicate_id_lists(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    client = _client(tmp_path, fake_profile_store)
    for value in (["record-a", "record-a"], ["record-a", 3]):
        response = client.post("/v0/profile/upsert", json=_body(delete_record_ids=value))
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
    assert fake_profile_store.write_calls == 0


def test_upsert_rejects_replace_mode_and_preserves_body_correlation_on_stale_error(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    client = _client(tmp_path, fake_profile_store)
    replace = client.post("/v0/profile/upsert", json=_body(mode="replace"))
    assert replace.status_code == 400

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    # The route client uses the same store; create one valid version first.
    from datetime import UTC, datetime

    from resume_agent.profile.models import (
        FieldType,
        FieldValue,
        Scope,
        Sensitivity,
        Source,
        SourceKind,
    )

    service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[
            FieldValue(
                id="person.full_name",
                label="姓名",
                field_type=FieldType.TEXT,
                value="Synthetic",
                scope=Scope.GLOBAL,
                sensitivity=Sensitivity.NORMAL,
                requires_confirmation=False,
                confirmed=True,
                source=Source(kind=SourceKind.MANUAL),
                updated_at=datetime(2099, 1, 1, tzinfo=UTC),
            )
        ],
        user_confirmed=True,
    )
    stale = client.post(
        "/v0/profile/upsert",
        json=_body(
            request_id="req-body-correlation",
            task_id="task-body-correlation",
            expected_profile_version=0,
        ),
    )
    assert stale.status_code == 409
    payload = stale.json()
    assert payload["request_id"] == "req-body-correlation"
    assert payload["task_id"] == "task-body-correlation"
    assert payload["failed_operation"] == "profile.upsert"
    assert "Synthetic" not in stale.text
