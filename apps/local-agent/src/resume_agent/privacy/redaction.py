"""Deterministic, non-mutating redaction primitives."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_MASK = "[REDACTED]"
_KEY_RE = re.compile(r"(?:token|secret|password|passwd|api[_-]?key|access[_-]?key|refresh[_-]?token|authorization|cookie|email|phone|mobile|name|address|resume|profile[_-]?value)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_ASSIGNMENT_RE = re.compile(r"\b(?:token|secret|password|passwd|api[_-]?key|access[_-]?key)\s*=\s*[^\s,;]+", re.IGNORECASE)
_TOKEN_RE = re.compile(r"\b(?:sk|pk|ghp|github_pat|token|key)[_-][A-Za-z0-9._~-]{6,}\b", re.IGNORECASE)
_ABS_PATH_RE = re.compile(r"(?:(?:[A-Za-z]:[\\/])|(?:/Users/)|(?:/home/)|(?:/var/)|(?:\\\\))[^\s,;]+")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")


def redact_text(value: str) -> str:
    """Mask common credentials, profile-like values, and absolute local paths."""
    if not isinstance(value, str):
        raise TypeError("redact_text expects str")
    result = _ABS_PATH_RE.sub(_MASK, value)
    result = _ASSIGNMENT_RE.sub(_MASK, result)
    result = _BEARER_RE.sub(_MASK, result)
    result = _TOKEN_RE.sub(_MASK, result)
    result = _EMAIL_RE.sub(_MASK, result)
    return _PHONE_RE.sub(_MASK, result)


def redact_details(value: Any) -> Any:
    """Return a JSON-safe redacted copy of nested mappings and sequences."""
    if isinstance(value, Mapping):
        return {
            str(key): _MASK if _KEY_RE.search(str(key)) else redact_details(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_details(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value


    raise TypeError(f"details contain non-JSON value: {type(value).__name__}")
_SAFE_OPERATION_KEYS = frozenset(
    {
        "operation",
        "status",
        "request_id",
        "task_id",
        "profile_id",
        "profile_version",
        "field_count",
        "error_code",
    }
)


def safe_operation_log(operation: str, **details: Any) -> dict[str, Any]:
    """Build metadata-only log fields; profile values and credentials are dropped."""

    if not isinstance(operation, str) or not operation.strip():
        raise ValueError("operation must be a non-empty string")
    payload: dict[str, Any] = {"operation": operation.strip()}
    for key, value in details.items():
        if key not in _SAFE_OPERATION_KEYS or key == "operation":
            continue
        if key in {"profile_version", "field_count"}:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                continue
            payload[key] = value
        elif isinstance(value, str):
            payload[key] = redact_text(value)
        elif value is not None:
            payload[key] = redact_details(value)
    return payload
