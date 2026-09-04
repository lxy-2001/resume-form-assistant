from pathlib import Path

from resume_agent.config import (
    DEFAULT_APP_NAME,
    DEFAULT_NAMESPACE,
    AppConfig,
)


def test_localhost_is_normalized_without_dns_lookup(tmp_path: Path) -> None:
    config = AppConfig(tmp_path, host="localhost")
    assert config.host == "127.0.0.1"


def test_name_namespace_defaults_and_mapping_aliases(tmp_path: Path) -> None:
    config = AppConfig.from_mapping(
        {"root": tmp_path, "name": "synthetic-app", "namespace": "synthetic_ns"}
    )
    assert config.app_name == "synthetic-app"
    assert config.name == "synthetic-app"
    assert config.namespace == "synthetic_ns"
    assert DEFAULT_APP_NAME != ""
    assert DEFAULT_NAMESPACE != ""


def test_safe_serialization_and_display_are_stable(tmp_path: Path) -> None:
    config = AppConfig(tmp_path, app_name="synthetic-app", namespace="synthetic_ns")
    first = config.to_dict()
    assert first == config.to_dict()
    assert str(tmp_path) not in repr(first)
    assert str(tmp_path) not in config.safe_display
    assert config.display == config.display
    assert config.to_dict(include_data_root=True)["data_root"] == str(tmp_path)
