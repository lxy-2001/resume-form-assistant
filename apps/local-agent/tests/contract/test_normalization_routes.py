from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.profile.service import ProfileService


def test_normalization_route_rejects_malformed_requests(fake_profile_store):
    client = TestClient(
        create_app(profile_service=ProfileService(fake_profile_store), require_loopback=False)
    )
    response = client.post(
        "/v0/profile/normalize/preview", json={"operation": "profile.normalize.preview"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"


def test_normalization_route_rejects_non_object_decision(fake_profile_store):
    client = TestClient(
        create_app(profile_service=ProfileService(fake_profile_store), require_loopback=False)
    )
    response = client.post(
        "/v0/profile/normalize/confirm",
        json={
            "schema_version": "0.1",
            "request_id": "req-invalid-decision",
            "task_id": "task-invalid-decision",
            "operation": "profile.normalize.confirm",
            "profile_id": "default-profile",
            "expected_profile_version": 0,
            "decisions": ["not-an-object"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
