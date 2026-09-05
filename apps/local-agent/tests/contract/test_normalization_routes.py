from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.profile.service import ProfileService


def test_normalization_route_rejects_malformed_requests(fake_profile_store):
    client = TestClient(create_app(profile_service=ProfileService(fake_profile_store), require_loopback=False))
    response = client.post("/v0/profile/normalize/preview", json={"operation": "profile.normalize.preview"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FIELD_VALUE"
