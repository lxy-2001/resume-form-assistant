from resume_agent.main import app


def test_placeholder_app_is_importable() -> None:
    assert app.title == "Resume Agent"
