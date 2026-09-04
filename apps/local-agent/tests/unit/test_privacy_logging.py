"""T025 tests for metadata-only, privacy-safe operation logging."""

from __future__ import annotations

import json

from resume_agent.privacy.redaction import safe_operation_log


def test_operation_log_allowlists_metadata_and_never_contains_profile_values() -> None:
    payload = safe_operation_log(
        "profile.upsert",
        status="completed",
        request_id="req-synthetic",
        profile_id="profile-synthetic",
        profile_version=2,
        field_count=1,
        fields=[{"id": "person.full_name", "value": "Synthetic Test Person"}],
        api_key="sk-synthetic-secret",
    )

    rendered = json.dumps(payload, ensure_ascii=False)
    assert payload == {
        "operation": "profile.upsert",
        "status": "completed",
        "request_id": "req-synthetic",
        "profile_id": "profile-synthetic",
        "profile_version": 2,
        "field_count": 1,
    }
    assert "Synthetic Test Person" not in rendered
    assert "sk-synthetic-secret" not in rendered


def test_operation_log_redacts_metadata_strings_and_does_not_mutate_input() -> None:
    details = {"status": "failed", "error_code": "token=synthetic-token", "field_count": 0}

    payload = safe_operation_log("profile.read", **details)

    assert details["error_code"] == "token=synthetic-token"
    assert "synthetic-token" not in json.dumps(payload)
