"""Contract-level regression tests for the extension/agent v0.1 boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "packages" / "contracts" / "v0.1" / "contracts.schema.json"
EXAMPLES_PATH = ROOT / "packages" / "contracts" / "v0.1" / "examples"


def load_master() -> dict:
    """Load the canonical schema with a useful RED-phase failure."""

    assert MASTER_PATH.is_file(), f"canonical contract schema is missing: {MASTER_PATH}"
    return json.loads(MASTER_PATH.read_text(encoding="utf-8"))


def validator_for(definition: str) -> Draft202012Validator:
    master = load_master()
    assert definition in master.get("$defs", {}), f"missing contract definition: {definition}"
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
    assert path.is_file(), f"contract example is missing: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonical_schema_is_valid_draft_2020_12() -> None:
    master = load_master()

    assert master["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(master)


@pytest.mark.parametrize(
    ("example_name", "definition"),
    [
        ("profile-upsert.json", "ProfileUpsertRequest"),
        ("scan-request.json", "ScanRequest"),
        ("match-response.json", "MatchResponse"),
        ("fill-plan.json", "FillPlan"),
        ("review-decision.json", "ReviewDecision"),
        ("execution-result.json", "ExecutionResult"),
    ],
)
def test_public_examples_validate_against_named_contracts(
    example_name: str, definition: str
) -> None:
    validator_for(definition).validate(load_example(example_name))


def test_fill_plan_cannot_enable_automatic_submission() -> None:
    payload = load_example("fill-plan.json")
    payload["auto_submit"] = True

    with pytest.raises(ValidationError):
        validator_for("FillPlan").validate(payload)


def test_execution_result_cannot_claim_that_a_submission_happened() -> None:
    payload = load_example("execution-result.json")
    payload["submitted"] = True

    with pytest.raises(ValidationError):
        validator_for("ExecutionResult").validate(payload)


def test_review_decision_requires_explicit_user_confirmation() -> None:
    payload = load_example("review-decision.json")
    payload["user_confirmed"] = False

    with pytest.raises(ValidationError):
        validator_for("ReviewDecision").validate(payload)


def test_uncertain_candidate_cannot_be_marked_as_not_requiring_confirmation() -> None:
    master = load_master()
    candidate = {
        "candidate_id": "candidate-uncertain",
        "page_field_id": "field-1",
        "value": "Example value",
        "confidence": 0.42,
        "source": {"kind": "agent", "detail": "ambiguous label"},
        "decision": "needs_confirmation",
        "requires_confirmation": False,
        "sensitivity": "normal",
        "reason": "The label has two plausible meanings.",
        "warnings": [],
    }
    root = {
        "$schema": master["$schema"],
        "$id": master["$id"],
        "$defs": master["$defs"],
        "$ref": "#/$defs/MatchCandidate",
    }

    with pytest.raises(ValidationError):
        Draft202012Validator(root, format_checker=FormatChecker()).validate(candidate)


def test_declarative_fill_actions_do_not_accept_executable_code() -> None:
    payload = load_example("fill-plan.json")
    payload["actions"][0]["script"] = "document.body.innerHTML = 'unexpected'"

    with pytest.raises(ValidationError):
        validator_for("FillPlan").validate(payload)
