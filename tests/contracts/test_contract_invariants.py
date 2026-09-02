"""Small invariants that prevent permissive-schema regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"


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


def envelope(operation: str) -> dict:
    return {
        "schema_version": "0.1",
        "request_id": "req-invariant-001",
        "task_id": "task-invariant-001",
        "operation": operation,
    }


def test_profile_upsert_rejects_an_empty_write_request() -> None:
    with pytest.raises(ValidationError):
        validator_for("ProfileUpsertRequest").validate(envelope("profile.upsert"))


def test_profile_upsert_allows_an_explicit_delete_request() -> None:
    payload = envelope("profile.upsert")
    payload["user_confirmed"] = True
    payload["delete_field_ids"] = ["person.full_name"]

    validator_for("ProfileUpsertRequest").validate(payload)


def test_undo_result_requires_a_token_when_it_is_restoring_actions() -> None:
    payload = {
        **envelope("fill.undo.result"),
        "actions": [
            {"action_id": "action-1", "status": "restored", "restored": True}
        ],
        "restored": True,
        "warnings": [],
    }

    with pytest.raises(ValidationError):
        validator_for("UndoResult").validate(payload)
