"""Boundary tests for the shared profile.upsert HTTP envelope."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
        "fields": [],
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
