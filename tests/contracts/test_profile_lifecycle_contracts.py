"""Contract tests for the F001 local-profile lifecycle boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"
EXAMPLES_PATH = ROOT / "packages" / "contracts" / "v0.1" / "examples"


def load_master() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validator_for(definition: str) -> Draft202012Validator:
    master = load_master()
    assert definition in master["$defs"], f"missing contract definition: {definition}"
    root = {
        "$schema": master["$schema"],
        "$id": master["$id"],
        "$defs": master["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    Draft202012Validator.check_schema(root)
    return Draft202012Validator(root, format_checker=FormatChecker())


def load_example(name: str) -> dict:
    path = EXAMPLES_PATH / name
    assert path.is_file(), f"missing lifecycle example: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def envelope(operation: str) -> dict:
    return {
        "schema_version": "0.1",
        "request_id": "req-profile-lifecycle-001",
        "task_id": "task-profile-lifecycle-001",
        "operation": operation,
    }


def confirmed_field(*, scope: str = "global", scope_context: str | None = None) -> dict:
    field = {
        "id": "person.full_name",
        "label": "示例姓名",
        "field_type": "text",
        "value": "示例用户",
        "scope": scope,
        "sensitivity": "normal",
        "requires_confirmation": False,
        "confirmed": True,
        "source": {"kind": "manual"},
        "updated_at": "2026-09-03T08:00:00Z",
    }
    if scope_context is not None:
        field["scope_context"] = scope_context
    return field


@pytest.mark.parametrize(
    ("example_name", "definition"),
    [
        ("profile-read.json", "ProfileReadRequest"),
        ("profile-read-response.json", "ProfileReadResponse"),
        ("profile-delete.json", "ProfileDeleteRequest"),
        ("profile-delete-response.json", "ProfileDeleteResponse"),
        ("profile-export.json", "ProfileExportRequest"),
        ("profile-export-response.json", "ProfileExportResponse"),
    ],
)
def test_profile_lifecycle_examples_validate(example_name: str, definition: str) -> None:
    validator_for(definition).validate(load_example(example_name))


def test_profile_read_is_read_only_and_needs_no_confirmation() -> None:
    request = {
        **envelope("profile.read"),
        "profile_id": "profile-main",
    }
    validator = validator_for("ProfileReadRequest")
    validator.validate(request)

    request["fields"] = [confirmed_field()]
    with pytest.raises(ValidationError):
        validator.validate(request)


def test_empty_profile_cannot_contain_saved_values_or_records() -> None:
    response = load_example("profile-read-response.json")
    response["profile"]["fields"] = [confirmed_field()]

    with pytest.raises(ValidationError):
        validator_for("ProfileReadResponse").validate(response)


def test_saved_profile_field_requires_confirmation_metadata() -> None:
    validator = validator_for("ProfileField")
    validator.validate(confirmed_field())

    unconfirmed = confirmed_field()
    unconfirmed["confirmed"] = False
    with pytest.raises(ValidationError):
        validator.validate(unconfirmed)


def test_scoped_profile_field_requires_exact_scope_context() -> None:
    validator = validator_for("ProfileField")

    with pytest.raises(ValidationError):
        validator.validate(confirmed_field(scope="website"))

    validator.validate(confirmed_field(scope="website", scope_context="website-example-careers"))

    with pytest.raises(ValidationError):
        validator.validate(confirmed_field(scope_context="unexpected-global-context"))


def test_field_value_selector_requires_scope_and_context_when_needed() -> None:
    validator = validator_for("ProfileDeleteSelection")
    validator.validate({"field_values": [{"id": "person.full_name", "scope": "global"}]})
    validator.validate(
        {
            "field_values": [
                {
                    "id": "custom.city",
                    "scope": "website",
                    "scope_context": "jobs-example",
                }
            ]
        }
    )

    for invalid in (
        {"field_values": [{"id": "custom.city"}]},
        {"field_values": [{"id": "custom.city", "scope": "website"}]},
        {
            "field_values": [
                {
                    "id": "custom.city",
                    "scope": "global",
                    "scope_context": "unexpected",
                }
            ]
        },
    ):
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_profile_upsert_requires_identity_and_optimistic_version() -> None:
    validator = validator_for("ProfileUpsertRequest")
    current_request = {
        **envelope("profile.upsert"),
        "profile_id": "profile-main",
        "expected_profile_version": 0,
        "user_confirmed": True,
        "fields": [confirmed_field()],
        "mode": "merge",
    }
    validator.validate(current_request)

    legacy_request = {
        **envelope("profile.upsert"),
        "user_confirmed": True,
        "delete_field_ids": ["person.full_name"],
    }
    with pytest.raises(ValidationError):
        validator.validate(legacy_request)


@pytest.mark.parametrize("user_confirmed", [False, None])
def test_profile_delete_requires_explicit_confirmation(
    user_confirmed: bool | None,
) -> None:
    request = load_example("profile-delete.json")
    if user_confirmed is None:
        request.pop("user_confirmed")
    else:
        request["user_confirmed"] = user_confirmed

    with pytest.raises(ValidationError):
        validator_for("ProfileDeleteRequest").validate(request)


def test_profile_delete_rejects_empty_or_ambiguous_selection() -> None:
    validator = validator_for("ProfileDeleteRequest")
    request = load_example("profile-delete.json")

    request["selection"] = {}
    with pytest.raises(ValidationError):
        validator.validate(request)

    request["selection"] = {
        "delete_all": True,
        "field_ids": ["person.full_name"],
    }
    with pytest.raises(ValidationError):
        validator.validate(request)


def test_partial_delete_result_must_explain_remaining_cleanup() -> None:
    response = load_example("profile-delete-response.json")
    response["task_state"] = "partial"
    response["warnings"] = []
    response["cleanup_pending"] = []

    with pytest.raises(ValidationError):
        validator_for("ProfileDeleteResponse").validate(response)


@pytest.mark.parametrize("user_confirmed", [False, None])
def test_profile_export_requires_explicit_confirmation(
    user_confirmed: bool | None,
) -> None:
    request = load_example("profile-export.json")
    if user_confirmed is None:
        request.pop("user_confirmed")
    else:
        request["user_confirmed"] = user_confirmed

    with pytest.raises(ValidationError):
        validator_for("ProfileExportRequest").validate(request)


def test_profile_export_rejects_empty_selection_and_remote_destination() -> None:
    validator = validator_for("ProfileExportRequest")
    request = load_example("profile-export.json")

    request["selection"] = {}
    with pytest.raises(ValidationError):
        validator.validate(request)

    request = load_example("profile-export.json")
    request["destination"]["path"] = "https://example.invalid/profile.json"
    with pytest.raises(ValidationError):
        validator.validate(request)

    request = load_example("profile-export.json")
    request["destination"] = {
        "kind": "remote_url",
        "path": "https://example.invalid/profile.json",
        "overwrite_existing": False,
    }
    with pytest.raises(ValidationError):
        validator.validate(request)

    for network_share_path in (
        r"\\server\share\profile.json",
        "//server/share/profile.json",
    ):
        request = load_example("profile-export.json")
        request["destination"]["path"] = network_share_path
        with pytest.raises(ValidationError):
            validator.validate(request)


@pytest.mark.parametrize("forbidden_property", ["contents", "upload_url"])
def test_profile_export_response_never_carries_data_or_upload_url(
    forbidden_property: str,
) -> None:
    response = load_example("profile-export-response.json")
    response[forbidden_property] = "synthetic-value"

    with pytest.raises(ValidationError):
        validator_for("ProfileExportResponse").validate(response)


def test_profile_lifecycle_error_codes_are_stable_and_bounded() -> None:
    validator = validator_for("ProfileLifecycleErrorCode")
    validator.validate("STALE_PROFILE_VERSION")
    validator.validate("STORAGE_UNAVAILABLE")

    with pytest.raises(ValidationError):
        validator.validate("SOME_UNDOCUMENTED_PROFILE_FAILURE")


def test_lifecycle_error_response_names_the_failed_operation() -> None:
    response = {
        **envelope("error"),
        "task_state": "failed",
        "failed_operation": "profile.delete",
        "error": {
            "code": "DELETE_FAILED",
            "message": "The synthetic profile could not be deleted.",
            "retryable": True,
        },
    }
    validator = validator_for("ErrorResponse")
    validator.validate(response)

    response["error"]["code"] = "SOME_UNDOCUMENTED_PROFILE_FAILURE"
    with pytest.raises(ValidationError):
        validator.validate(response)
