from pathlib import Path

from fastapi.testclient import TestClient

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.errors import ProfileNotFoundError


def _client(
    tmp_path: Path,
    *,
    request_limit: int = 1_048_576,
    allowed_origins: set[str] | None = None,
) -> TestClient:
    config = AppConfig(tmp_path, request_limit=request_limit)
    return TestClient(
        create_app(config, allowed_origins=allowed_origins),
        client=("127.0.0.1", 1234),
        raise_server_exceptions=False,
    )


def test_health_has_no_profile_data(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "schema_version": "0.1"}


def test_rejects_non_loopback_client(tmp_path: Path) -> None:
    client = TestClient(
        create_app(AppConfig(tmp_path)),
        client=("10.0.0.8", 1234),
        raise_server_exceptions=False,
    )
    response = client.get("/health")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOOPBACK_REQUIRED"


def test_rejects_unallowlisted_origin(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/health", headers={"origin": "https://evil.example"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_accepts_explicit_origin_allowlist(tmp_path: Path) -> None:
    client = _client(tmp_path, allowed_origins={"chrome-extension://synthetic"})
    response = client.get("/health", headers={"origin": "chrome-extension://synthetic"})
    assert response.status_code == 200


def test_rejects_oversize_declared_body_without_echoing_body(tmp_path: Path) -> None:
    response = _client(tmp_path, request_limit=4).post("/health", content=b"secret-synthetic")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert "secret-synthetic" not in response.text


def test_typed_error_is_contract_shaped_and_redacted(tmp_path: Path) -> None:
    app = create_app(AppConfig(tmp_path))

    @app.get("/synthetic-error")
    async def synthetic_error() -> None:
        raise ProfileNotFoundError(
            message="missing person@example.test at C:/Users/demo/profile.json",
            details={"email": "person@example.test", "count": 0},
        )

    response = TestClient(
        app,
        client=("127.0.0.1", 1234),
        raise_server_exceptions=False,
    ).get("/synthetic-error", headers={"x-operation": "profile.read"})
    payload = response.json()
    assert response.status_code == 409
    assert payload["schema_version"] == "0.1"
    assert payload["operation"] == "error"
    assert payload["failed_operation"] == "profile.read"
    assert payload["error"]["code"] == "PROFILE_NOT_FOUND"
    assert "person@example.test" not in response.text
    assert "C:/Users/demo/profile.json" not in response.text


def test_factory_does_not_require_existing_data_root(tmp_path: Path) -> None:
    root = tmp_path / "not-created"
    app = create_app(AppConfig(root))
    assert root.exists() is False
    assert app.title == "resume-agent"
