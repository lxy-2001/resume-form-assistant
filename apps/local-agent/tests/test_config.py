from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from resume_agent.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_REQUEST_LIMIT,
    AppConfig,
    answers_path,
    artifacts_path,
    profile_path,
    user_data_path,
)


def test_defaults_are_deterministic_and_displayable(tmp_path: Path) -> None:
    config = AppConfig(tmp_path.absolute())
    assert config.host == DEFAULT_HOST == "127.0.0.1"
    assert config.port == DEFAULT_PORT
    assert config.request_limit == DEFAULT_REQUEST_LIMIT
    assert config.display == f"http://127.0.0.1:{DEFAULT_PORT}"


def test_config_is_immutable_and_root_is_absolute(tmp_path: Path) -> None:
    config = AppConfig(tmp_path.absolute())
    with pytest.raises(FrozenInstanceError):
        config.port = 1234  # type: ignore[misc]
    with pytest.raises(ValueError, match="absolute"):
        AppConfig(Path("relative-root"))


@pytest.mark.parametrize("host", ["0.0.0.0", "localhost", "192.168.1.2"])
def test_only_loopback_host_is_allowed(tmp_path: Path, host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        AppConfig(tmp_path.absolute(), host=host)



def test_ipv6_loopback_is_allowed(tmp_path: Path) -> None:
    assert AppConfig(tmp_path.absolute(), host="::1").host == "::1"

@pytest.mark.parametrize("port", [0, 65536, -1, True, "8765"])
def test_port_is_safe(tmp_path: Path, port: object) -> None:
    with pytest.raises(ValueError, match="port"):
        AppConfig(tmp_path.absolute(), port=port)  # type: ignore[arg-type]


@pytest.mark.parametrize("limit", [0, -1, 100 * 1024 * 1024 + 1, False, "1"])
def test_request_limit_is_safe(tmp_path: Path, limit: object) -> None:
    with pytest.raises(ValueError, match="request_limit"):
        AppConfig(tmp_path.absolute(), request_limit=limit)  # type: ignore[arg-type]


def test_helpers_are_deterministic_and_contained(tmp_path: Path) -> None:
    config = AppConfig(tmp_path.absolute())
    assert profile_path(config) == tmp_path / "profile.json"
    assert answers_path(config) == tmp_path / "answers.json"
    assert artifacts_path(config) == tmp_path / "artifacts"
    assert user_data_path(config, "nested", "x.json") == tmp_path / "nested" / "x.json"
    assert config.temp_path().is_relative_to(tmp_path)
    assert config.backup_path().is_relative_to(tmp_path)
    assert config.recovery_path().is_relative_to(tmp_path)
    assert config.lock_path().is_relative_to(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        user_data_path(config, "..", "outside.json")
    with pytest.raises(ValueError, match="escapes"):
        user_data_path(config, Path("C:/outside.json"))


def test_helpers_do_not_require_existing_root(tmp_path: Path) -> None:
    root = tmp_path / "not-created"
    config = AppConfig(root.absolute())
    assert profile_path(config) == root / "profile.json"
    assert not root.exists()
