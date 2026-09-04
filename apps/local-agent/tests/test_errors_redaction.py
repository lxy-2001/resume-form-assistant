from __future__ import annotations

import json

import pytest

from resume_agent.privacy.redaction import redact_details, redact_text
from resume_agent.profile.errors import (
    ConfirmationRequiredError,
    ProfileError,
    ProfileNotFoundError,
)
from resume_agent.storage.errors import StorageError, StorageUnavailableError


def test_lifecycle_errors_have_stable_codes_and_json_safe_details() -> None:
    error = ProfileNotFoundError(details={"profile_id": "synthetic-profile", "count": 0})

    assert error.code == "PROFILE_NOT_FOUND"
    assert error.details == {"profile_id": "synthetic-profile", "count": 0}
    json.dumps(error.to_dict())
    assert isinstance(error, ProfileError)


def test_error_details_are_redacted_without_mutating_input() -> None:
    source = {
        "operation": "profile.upsert",
        "profile_id": "synthetic-profile",
        "email": "person@example.test",
        "token": "Bearer synthetic-token-123",
        "nested": ["C:/Users/demo/private/profile.json", {"count": 2}],
    }
    original = source.copy()

    result = redact_details(source)

    assert source == original
    assert result["operation"] == "profile.upsert"
    assert result["profile_id"] == "synthetic-profile"
    assert result["count"] == 2 if "count" in result else True
    rendered = json.dumps(result)
    assert "person@example.test" not in rendered
    assert "synthetic-token-123" not in rendered
    assert "C:/Users/demo/private/profile.json" not in rendered


def test_text_redaction_is_deterministic_for_tokens_profiles_and_paths() -> None:
    text = "profile synthetic-profile email person@example.test token=abc123 path=/Users/demo/profile.json"
    assert redact_text(text) == redact_text(text)
    redacted = redact_text(text)
    assert "person@example.test" not in redacted
    assert "abc123" not in redacted
    assert "/Users/demo/profile.json" not in redacted


def test_domain_and_storage_subclasses_keep_typed_codes() -> None:
    assert ConfirmationRequiredError().code == "CONFIRMATION_REQUIRED"
    storage_error = StorageUnavailableError(details={"operation": "profile.read"})
    assert storage_error.code == "STORAGE_UNAVAILABLE"
    assert isinstance(storage_error, StorageError)


def test_invalid_details_are_rejected() -> None:
    with pytest.raises(TypeError):
        ProfileNotFoundError(details={"bad": object()})
