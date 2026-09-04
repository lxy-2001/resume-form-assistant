"""Contract boundary tests for identifier and revision constraints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-route-id-validation"


def _client(tmp_path: Path, store: ProfileStore) -> TestClient:
    from resume_agent.profile.service import ProfileService

    return TestClient(
        create_app(
            AppConfig(tmp_path),
            profile_service=ProfileService(store, profile_id=PROFILE_ID),
        ),
        client=("127.0.0.1", 1234),
        raise_server_exceptions=False,
    )


def _body(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "0.1",
        "request_id": "req-route-id-validation",
        "task_id": "task-route-id-validation",
        "operation": "profile.upsert",
        "profile_id": PROFILE_ID,
        "expected_profile_version": 0,
        "user_confirmed": True,
        "mode": "merge",
        "fields": [
            {
                "id": "person.full_name",
                "value": "Synthetic User",
                "confirmed": True,
                "source": {"kind": "manual"},
            }
        ],
    }
    body.update(changes)
    return body


def test_upsert_rejects_negative_revision_and_non_contract_ids(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    client = _client(tmp_path, fake_profile_store)

    for body in (
        _body(expected_profile_version=-1),
        _body(profile_id="profile/with-slash"),
        _body(request_id="request/with-slash"),
    ):
        response = client.post("/v0/profile/upsert", json=body)
        assert response.status_code == 400

    assert fake_profile_store.write_calls == 0


def test_upsert_rejects_non_contract_scope_context_without_mutation(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    client = _client(tmp_path, fake_profile_store)
    response = client.post(
        "/v0/profile/upsert",
        json=_body(
            fields=[
                {
                    "id": "application.expected_salary",
                    "value": "Synthetic",
                    "scope": "application",
                    "scope_context": "application/with-slash",
                    "confirmed": True,
                    "source": {"kind": "manual"},
                }
            ]
        ),
    )

    assert response.status_code == 400
    assert fake_profile_store.write_calls == 0


@pytest.mark.parametrize(
    "invalid_id",
    [
        "",
        " leading-space",
        "trailing-space ",
        "profile/with-slash",
        "profile\\with-backslash",
        "中文-profile",
        "-leading-hyphen",
        "_leading-underscore",
        "a" * 129,
    ],
)
def test_upsert_rejects_every_invalid_contract_id_without_mutation(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
    invalid_id: str,
) -> None:
    client = _client(tmp_path, fake_profile_store)
    response = client.post(
        "/v0/profile/upsert",
        json=_body(
            request_id=invalid_id,
            task_id=invalid_id,
            profile_id=invalid_id,
            fields=[
                {
                    "id": invalid_id,
                    "value": "Synthetic User",
                    "confirmed": True,
                    "source": {"kind": "manual"},
                }
            ],
        ),
    )

    assert response.status_code == 400
    assert fake_profile_store.write_calls == 0


@pytest.mark.parametrize("invalid_revision", [True, -1, 1.0, "0", None])
def test_upsert_rejects_non_contract_revision_without_mutation(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
    invalid_revision: object,
) -> None:
    client = _client(tmp_path, fake_profile_store)
    response = client.post(
        "/v0/profile/upsert",
        json=_body(expected_profile_version=invalid_revision),
    )

    assert response.status_code == 400
    assert fake_profile_store.write_calls == 0


def test_route_accepts_boundary_length_and_allowed_id_characters(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    boundary_id = "A" + ("a" * 126) + ":"
    client = _client(tmp_path, fake_profile_store)
    response = client.post(
        "/v0/profile/upsert",
        json=_body(request_id=boundary_id, task_id=boundary_id),
    )

    assert response.status_code == 200


def test_models_apply_contract_id_and_revision_constraints() -> None:
    from datetime import UTC, datetime

    from resume_agent.profile.models import (
        FieldType,
        FieldValue,
        ProfileSnapshot,
        Scope,
        Sensitivity,
        Source,
    )

    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    valid = {
        "id": "person.full_name",
        "label": "姓名",
        "field_type": FieldType.TEXT,
        "value": "Synthetic User",
        "scope": Scope.GLOBAL,
        "sensitivity": Sensitivity.NORMAL,
        "requires_confirmation": False,
        "confirmed": True,
        "source": Source(kind="manual"),
        "updated_at": timestamp,
    }
    with pytest.raises(ValueError):
        FieldValue.model_validate({**valid, "id": "field/invalid"})
    with pytest.raises(ValueError):
        ProfileSnapshot(
            profile_id="profile/invalid",
            profile_version=0,
            fields=[],
            records=[],
            field_definitions=[],
            created_at=timestamp,
            updated_at=timestamp,
        )
    with pytest.raises(ValueError):
        ProfileSnapshot(
            profile_id="profile-valid",
            profile_version=True,
            fields=[],
            records=[],
            field_definitions=[],
            created_at=timestamp,
            updated_at=timestamp,
        )
