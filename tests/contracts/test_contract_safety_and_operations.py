"""Coverage for the less frequently used v0.1 operations and privacy gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"
EXAMPLES_PATH = ROOT / "packages" / "contracts" / "v0.1" / "examples"


def validator_for(definition: str) -> Draft202012Validator:
    master = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    root = {
        "$schema": master["$schema"],
        "$id": master["$id"],
        "$defs": master["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    Draft202012Validator.check_schema(root)
    return Draft202012Validator(root, format_checker=FormatChecker())


def example(name: str) -> dict:
    return json.loads((EXAMPLES_PATH / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("example_name", "definition"),
    [
        ("profile-import-preview-request.json", "ProfileImportPreviewRequest"),
        ("profile-import-preview.json", "ProfileImportPreview"),
        ("profile-import-confirm.json", "ProfileImportConfirmRequest"),
        ("scan-response.json", "ScanResponse"),
        ("match-request.json", "MatchRequest"),
        ("undo-request.json", "UndoRequest"),
        ("undo-result.json", "UndoResult"),
        ("error-response.json", "ErrorResponse"),
    ],
)
def test_remaining_public_operation_examples_validate(
    example_name: str, definition: str
) -> None:
    validator_for(definition).validate(example(example_name))


def test_import_candidate_must_wait_for_user_confirmation() -> None:
    payload = example("profile-import-preview.json")
    payload["candidates"][0]["requires_confirmation"] = False

    with pytest.raises(ValidationError):
        validator_for("ProfileImportPreview").validate(payload)


def test_import_preview_can_carry_local_file_content_without_changing_source_metadata() -> None:
    payload = example("profile-import-preview-request.json")
    payload["content_base64"] = "c3ludGhldGljLXBkZg=="

    validator_for("ProfileImportPreviewRequest").validate(payload)


def test_import_preview_rejects_non_base64_content() -> None:
    payload = example("profile-import-preview-request.json")
    payload["content_base64"] = "not base64!"

    with pytest.raises(ValidationError):
        validator_for("ProfileImportPreviewRequest").validate(payload)


def test_remote_model_consent_requires_explicit_user_approval() -> None:
    validator = validator_for("Consent")

    validator.validate(
        {
            "remote_model_allowed": True,
            "user_consented": True,
            "purpose": "matching",
        }
    )

    with pytest.raises(ValidationError):
        validator.validate({"remote_model_allowed": True, "user_consented": False, "purpose": "matching"})

    with pytest.raises(ValidationError):
        validator.validate({"remote_model_allowed": False, "user_consented": True})


def test_existing_page_value_requires_a_fill_precondition() -> None:
    payload = example("fill-plan.json")
    payload["actions"][0]["precondition"] = {"current_value_present": True}

    with pytest.raises(ValidationError):
        validator_for("FillPlan").validate(payload)


def test_undo_request_also_requires_explicit_confirmation() -> None:
    payload = example("undo-request.json")
    payload["user_confirmed"] = False

    with pytest.raises(ValidationError):
        validator_for("UndoRequest").validate(payload)
