"""Cross-cutting privacy invariants expressed at the message boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"


def validator_for(definition: str) -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    root = {
        "$schema": schema["$schema"],
        "$id": schema["$id"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    Draft202012Validator.check_schema(root)
    return Draft202012Validator(root, format_checker=FormatChecker())


def test_remote_match_result_needs_provider_and_consent_record() -> None:
    payload = {
        "schema_version": "0.1",
        "request_id": "req-remote-001",
        "task_id": "task-remote-001",
        "operation": "page.match.result",
        "candidates": [],
        "unsupported": [],
        "warnings": [],
        "model_used": True,
        "remote_data_sent": True,
        "consent_recorded": False,
    }

    with pytest.raises(ValidationError):
        validator_for("MatchResponse").validate(payload)


def test_remote_import_result_needs_provider_and_consent_record() -> None:
    payload = {
        "schema_version": "0.1",
        "request_id": "req-remote-import-001",
        "task_id": "task-remote-import-001",
        "operation": "profile.import.preview.result",
        "document_id": "doc-example-001",
        "candidates": [],
        "warnings": [],
        "remote_data_sent": True,
        "consent_recorded": False,
    }

    with pytest.raises(ValidationError):
        validator_for("ProfileImportPreview").validate(payload)


def test_sensitive_profile_field_cannot_disable_confirmation() -> None:
    payload = {
        "id": "person.id_number",
        "label": "示例证件号码",
        "field_type": "text",
        "value": "EXAMPLE-IDENTIFIER",
        "scope": "global",
        "sensitivity": "highly_sensitive",
        "requires_confirmation": True,
        "confirmed": True,
        "source": {"kind": "manual"},
        "updated_at": "2026-09-03T08:00:00Z",
    }

    validator = validator_for("ProfileField")
    validator.validate(payload)

    payload["requires_confirmation"] = False
    with pytest.raises(ValidationError):
        validator.validate(payload)
