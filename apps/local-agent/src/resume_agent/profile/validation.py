"""Deterministic validation for persisted profile values.

Validation is intentionally local and side-effect free.  Error details describe the
constraint that failed but never include the candidate value itself.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from urllib.parse import urlparse

from resume_agent.profile.errors import InvalidFieldValueError
from resume_agent.profile.models import (
    FieldDefinition,
    FieldType,
    FieldValue,
    PageOption,
    ValidationRule,
)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()-]{6,24}$")


def _invalid(field_type: FieldType, reason: str) -> InvalidFieldValueError:
    return InvalidFieldValueError(
        "field value failed validation",
        details={"field_type": field_type.value, "reason": reason},
    )


def _rule(value: ValidationRule | Mapping[str, Any] | None) -> ValidationRule | None:
    if value is None:
        return None
    return value if isinstance(value, ValidationRule) else ValidationRule.model_validate(value)


def _option_values(options: Sequence[Any] | None) -> list[Any] | None:
    if options is None:
        return None
    values: list[Any] = []
    for option in options:
        if isinstance(option, PageOption):
            values.append(option.value)
        elif isinstance(option, Mapping) and "value" in option:
            values.append(option["value"])
        else:
            values.append(option)
    return values


def _check_common(value: str, field_type: FieldType, rule: ValidationRule | None) -> str:
    normalized = value.strip()
    if not normalized:
        raise _invalid(field_type, "blank")
    if rule is not None:
        if rule.min_length is not None and len(normalized) < rule.min_length:
            raise _invalid(field_type, "too_short")
        if rule.max_length is not None and len(normalized) > rule.max_length:
            raise _invalid(field_type, "too_long")
        if rule.pattern is not None:
            try:
                matched = re.fullmatch(rule.pattern, normalized)
            except re.error as exc:
                raise _invalid(field_type, "invalid_rule") from exc
            if matched is None:
                raise _invalid(field_type, "pattern")
    return normalized


def _check_allowed(value: Any, field_type: FieldType, rule: ValidationRule | None, options: list[Any] | None) -> None:
    allowed = options
    if rule is not None and rule.allowed_values is not None:
        allowed = list(rule.allowed_values)
    if allowed is not None and value not in allowed:
        raise _invalid(field_type, "not_allowed")


def _check_number(value: float, field_type: FieldType, rule: ValidationRule | None) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _invalid(field_type, "type")
    if rule is not None:
        if rule.minimum is not None and value < rule.minimum:
            raise _invalid(field_type, "below_minimum")
        if rule.maximum is not None and value > rule.maximum:
            raise _invalid(field_type, "above_maximum")
    return value


def validate_value(
    field_type: FieldType | str,
    value: Any,
    rule: ValidationRule | Mapping[str, Any] | None = None,
    *,
    options: Sequence[Any] | None = None,
) -> Any:
    """Return a normalized value or raise a privacy-safe ``InvalidFieldValueError``."""

    try:
        kind = field_type if isinstance(field_type, FieldType) else FieldType(field_type)
    except ValueError as exc:
        raise InvalidFieldValueError("unsupported field type", details={"reason": "type"}) from exc
    constraints = _rule(rule)
    allowed = _option_values(options)

    if kind in {FieldType.TEXT, FieldType.RICH_TEXT}:
        if not isinstance(value, str):
            raise _invalid(kind, "type")
        normalized = _check_common(value, kind, constraints)
        if constraints is not None and constraints.format == "url":
            parsed_url = urlparse(normalized)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise _invalid(kind, "format")
        elif constraints is not None and constraints.format == "postal_code":
            if not re.fullmatch(r"\\d{6}", normalized):
                raise _invalid(kind, "format")
        elif constraints is not None and constraints.format not in (None, ""):
            raise _invalid(kind, "format")
        _check_allowed(normalized, kind, constraints, allowed)
        return normalized

    if kind is FieldType.EMAIL:
        if not isinstance(value, str):
            raise _invalid(kind, "type")
        normalized = _check_common(value, kind, constraints)
        if not _EMAIL_RE.fullmatch(normalized):
            raise _invalid(kind, "format")
        _check_allowed(normalized, kind, constraints, allowed)
        return normalized

    if kind is FieldType.PHONE:
        if not isinstance(value, str):
            raise _invalid(kind, "type")
        normalized = _check_common(value, kind, constraints)
        if not _PHONE_RE.fullmatch(normalized):
            raise _invalid(kind, "format")
        _check_allowed(normalized, kind, constraints, allowed)
        return normalized

    if kind is FieldType.DATE:
        if not isinstance(value, str):
            raise _invalid(kind, "type")
        normalized = _check_common(value, kind, constraints)
        try:
            parsed = date.fromisoformat(normalized)
        except ValueError as exc:
            raise _invalid(kind, "format") from exc
        normalized = parsed.isoformat()
        _check_allowed(normalized, kind, constraints, allowed)
        return normalized

    if kind is FieldType.YEAR:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise _invalid(kind, "type")
        if isinstance(value, str):
            text = _check_common(value, kind, constraints)
            if not text.isdigit():
                raise _invalid(kind, "format")
            normalized_year = int(text)
        else:
            normalized_year = value
        if not 1000 <= normalized_year <= 9999:
            raise _invalid(kind, "range")
        _check_allowed(normalized_year, kind, constraints, allowed)
        return normalized_year

    if kind is FieldType.NUMBER:
        normalized_number = _check_number(value, kind, constraints)
        _check_allowed(normalized_number, kind, constraints, allowed)
        return normalized_number

    if kind is FieldType.BOOLEAN:
        if not isinstance(value, bool):
            raise _invalid(kind, "type")
        _check_allowed(value, kind, constraints, allowed)
        return value

    if kind is FieldType.ENUM:
        if not isinstance(value, (str, int, float, bool)):
            raise _invalid(kind, "type")
        if allowed is None and (constraints is None or constraints.allowed_values is None):
            raise _invalid(kind, "options_required")
        _check_allowed(value, kind, constraints, allowed)
        return value

    if kind is FieldType.MULTIVALUE:
        if not isinstance(value, (list, tuple)) or not value:
            raise _invalid(kind, "type_or_empty")
        normalized_values = list(value)
        if len({repr(item) for item in normalized_values}) != len(normalized_values):
            raise _invalid(kind, "duplicate")
        for item in normalized_values:
            _check_allowed(item, kind, constraints, allowed)
        return normalized_values

    if kind is FieldType.OBJECT:
        if not isinstance(value, Mapping):
            raise _invalid(kind, "type")
        return dict(value)

    raise _invalid(kind, "unsupported")


def validate_field_value(field: FieldValue, definition: FieldDefinition | None = None) -> FieldValue:
    """Validate and return a copied field with a normalized value."""

    field_type = definition.field_type if definition is not None else field.field_type
    rule = definition.validation if definition is not None else field.validation
    options = definition.options if definition is not None else field.options
    normalized = validate_value(field_type, field.value, rule, options=options)
    if normalized == field.value:
        return field
    return field.model_copy(update={"value": normalized, "field_type": field_type})


__all__ = ["validate_field_value", "validate_value"]
