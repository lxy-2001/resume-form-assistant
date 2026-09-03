"""Ensure consumers can validate messages against the master file directly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"
EXAMPLES_PATH = ROOT / "packages" / "contracts" / "v0.1" / "examples"


def master_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_master_schema_accepts_each_public_message_example() -> None:
    validator = master_validator()
    for path in sorted(EXAMPLES_PATH.glob("*.json")):
        validator.validate(json.loads(path.read_text(encoding="utf-8")))


def test_master_schema_rejects_an_unknown_operation() -> None:
    payload = {
        "schema_version": "0.1",
        "request_id": "req-unknown-001",
        "task_id": "task-unknown-001",
        "operation": "page.submit",
    }

    with pytest.raises(ValidationError):
        master_validator().validate(payload)
