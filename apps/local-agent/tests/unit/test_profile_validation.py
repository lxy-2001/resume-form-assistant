"""T014 tests fixing the deterministic field validation contract."""

from __future__ import annotations

import pytest

from resume_agent.profile.errors import InvalidFieldValueError
from resume_agent.profile.models import FieldType, ValidationRule
from resume_agent.profile.validation import validate_value


@pytest.mark.parametrize(
    ("field_type", "value", "expected"),
    [
        (FieldType.TEXT, "  Synthetic Person  ", "Synthetic Person"),
        (FieldType.EMAIL, "person@example.invalid", "person@example.invalid"),
        (FieldType.DATE, "2099-01-31", "2099-01-31"),
        (FieldType.YEAR, 2099, 2099),
        (FieldType.NUMBER, 3.5, 3.5),
        (FieldType.BOOLEAN, True, True),
        (FieldType.ENUM, "alpha", "alpha"),
        (FieldType.MULTIVALUE, ["alpha", "beta"], ["alpha", "beta"]),
    ],
)
def test_supported_types_return_safe_normalized_values(
    field_type: FieldType,
    value: object,
    expected: object,
) -> None:
    options = ["alpha", "beta"] if field_type in {FieldType.ENUM, FieldType.MULTIVALUE} else None

    assert validate_value(field_type, value, options=options) == expected


@pytest.mark.parametrize(
    ("field_type", "value"),
    [
        (FieldType.TEXT, "   "),
        (FieldType.EMAIL, "not-an-email"),
        (FieldType.DATE, "2099-02-31"),
        (FieldType.YEAR, 99),
        (FieldType.NUMBER, True),
        (FieldType.BOOLEAN, "true"),
        (FieldType.ENUM, "gamma"),
        (FieldType.MULTIVALUE, []),
        (FieldType.MULTIVALUE, ["alpha", "alpha"]),
    ],
)
def test_invalid_type_or_format_raises_privacy_safe_error(
    field_type: FieldType,
    value: object,
) -> None:
    options = ["alpha", "beta"] if field_type in {FieldType.ENUM, FieldType.MULTIVALUE} else None

    with pytest.raises(InvalidFieldValueError) as caught:
        validate_value(field_type, value, options=options)

    error = caught.value
    assert error.code == "INVALID_FIELD_VALUE"
    assert error.message
    assert error.details.get("field_type") == field_type.value
    assert "gamma" not in str(error.details)
    assert "not-an-email" not in str(error.details)


def test_validation_rule_enforces_text_length_and_pattern() -> None:
    rule = ValidationRule(min_length=3, max_length=12, pattern=r"^[A-Z][A-Za-z ]+$")

    assert validate_value(FieldType.TEXT, "Synthetic", rule=rule) == "Synthetic"
    for candidate in ("No", "this contains 9"):
        with pytest.raises(InvalidFieldValueError):
            validate_value(FieldType.TEXT, candidate, rule=rule)


def test_validation_rule_enforces_numeric_range() -> None:
    rule = ValidationRule(minimum=1, maximum=5)

    assert validate_value(FieldType.NUMBER, 3, rule=rule) == 3
    for candidate in (0, 6):
        with pytest.raises(InvalidFieldValueError):
            validate_value(FieldType.NUMBER, candidate, rule=rule)


def test_allowed_values_are_applied_to_enum_and_multivalue() -> None:
    rule = ValidationRule(allowed_values=["alpha", "beta"])

    assert validate_value(FieldType.ENUM, "alpha", rule=rule) == "alpha"
    assert validate_value(FieldType.MULTIVALUE, ["alpha", "beta"], rule=rule) == ["alpha", "beta"]
    with pytest.raises(InvalidFieldValueError):
        validate_value(FieldType.ENUM, "gamma", rule=rule)
    with pytest.raises(InvalidFieldValueError):
        validate_value(FieldType.MULTIVALUE, ["alpha", "gamma"], rule=rule)

