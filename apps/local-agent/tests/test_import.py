from resume_agent.config import DEFAULT_APP_NAME
from resume_agent.main import _allowed_origins, app


def test_runtime_app_is_importable() -> None:
    assert app.title == DEFAULT_APP_NAME


def test_environment_origins_preserve_config_data_root(monkeypatch, tmp_path) -> None:
    from resume_agent.config import AppConfig

    config = AppConfig(tmp_path)
    monkeypatch.setenv("RESUME_AGENT_ALLOWED_ORIGINS", "chrome-extension://synthetic")

    assert _allowed_origins(config) == ("chrome-extension://synthetic",)
