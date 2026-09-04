"""Contract boundary cases where one US2 mutation member is sufficient."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-route-defaults"
TS = "2099-01-01T00:00:00Z"


def _client(tmp_path: Path, store: ProfileStore) -> TestClient:
    service = ProfileService(store, profile_id=PROFILE_ID)
    return TestClient(
        create_app(AppConfig(tmp_path), profile_service=service),
        client=("127.0.0.1", 1234),
        raise_server_exceptions=False,
    )


def _record() -> dict[str, Any]:
    return {
        "record_id": "education-route-defaults-001",
        "record_type": "education",
        "position": 0,
        "fields": [
            {
                "id": "education.school_name",
                "label": "院校/培养单位",
                "field_type": "text",
                "value": "Synthetic University",
                "scope": "global",
                "sensitivity": "normal",
                "requires_confirmation": False,
                "confirmed": True,
                "source": {"kind": "manual"},
                "updated_at": TS,
            }
        ],
        "confirmed": True,
        "created_at": TS,
        "updated_at": TS,
    }


def test_records_only_upsert_is_accepted_when_fields_are_omitted(
    tmp_path: Path,
    fake_profile_store: ProfileStore,
) -> None:
    """The schema permits a records-only mutation; the route must default fields to []."""

    response = _client(tmp_path, fake_profile_store).post(
        "/v0/profile/upsert",
        json={
            "schema_version": "0.1",
            "request_id": "req-route-defaults",
            "task_id": "task-route-defaults",
            "operation": "profile.upsert",
            "profile_id": PROFILE_ID,
            "expected_profile_version": 0,
            "user_confirmed": True,
            "mode": "merge",
            "records": [_record()],
        },
    )

    assert response.status_code == 200
    assert response.json()["written_record_ids"] == ["education-route-defaults-001"]
