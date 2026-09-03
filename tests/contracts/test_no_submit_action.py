"""The v0.1 action vocabulary must never grow a submission operation silently."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"
EXAMPLE_PATH = ROOT / "packages" / "contracts" / "v0.1" / "examples" / "fill-plan.json"


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    root = {
        "$schema": schema["$schema"],
        "$id": schema["$id"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/FillPlan",
    }
    Draft202012Validator.check_schema(root)
    return Draft202012Validator(root, format_checker=FormatChecker())


def test_submit_is_not_a_fill_action_operation() -> None:
    payload = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    payload["actions"][0]["operation"] = "submit"

    with pytest.raises(ValidationError):
        validator().validate(payload)
