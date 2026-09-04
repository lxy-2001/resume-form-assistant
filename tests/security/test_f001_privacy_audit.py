"""T049 synthetic-data and secret-surface audit for F001."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk)-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
)
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".json", ".md", ".toml", ".yml", ".yaml"}


def _tracked_text_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return [
        REPO_ROOT / raw.decode("utf-8")
        for raw in result.stdout.split(b"\0")
        if raw and Path(raw.decode("utf-8")).suffix.lower() in TEXT_SUFFIXES
    ]


def test_tracked_sources_contain_no_private_key_or_common_api_token_patterns() -> None:
    for path in _tracked_text_files():
        text = path.read_text(encoding="utf-8")
        assert not any(pattern.search(text) for pattern in SECRET_PATTERNS), path


def test_f001_fixtures_are_explicitly_synthetic_and_use_non_deliverable_domains() -> None:
    fixture = (REPO_ROOT / "apps/local-agent/tests/fixtures/f001_profiles.py").read_text(encoding="utf-8")
    assert "Synthetic" in fixture
    assert ".invalid" in fixture
    assert "真实" not in fixture
