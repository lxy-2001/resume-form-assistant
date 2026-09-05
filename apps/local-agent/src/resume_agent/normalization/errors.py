"""Stable, privacy-safe error categories for normalization boundaries."""

from __future__ import annotations

from enum import StrEnum


class NormalizationErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_FIELD_VALUE"
    TASK_UNAVAILABLE = "TASK_UNAVAILABLE"
    TASK_EXPIRED = "TASK_EXPIRED"
    STALE_PROFILE = "STALE_PROFILE_VERSION"
    STORAGE_FAILURE = "STORAGE_FAILURE"
    UNSUPPORTED_SEMANTICS = "UNSUPPORTED_SEMANTICS"


__all__ = ["NormalizationErrorCode"]
