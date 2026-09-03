"""Typed, privacy-safe profile lifecycle errors."""

from __future__ import annotations

from typing import Any, ClassVar

from resume_agent.privacy.redaction import redact_details, redact_text


class LifecycleError(Exception):
    code: ClassVar[str] = "LIFECYCLE_ERROR"

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None) -> None:
        self.message = redact_text(message or self.code)
        self.details = redact_details(details or {})
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": redact_details(self.details)}


class ProfileError(LifecycleError):
    """Base class for domain/profile failures."""


class ProfileNotFoundError(ProfileError):
    code = "PROFILE_NOT_FOUND"


class ConfirmationRequiredError(ProfileError):
    code = "CONFIRMATION_REQUIRED"


class StaleProfileVersionError(ProfileError):
    code = "STALE_PROFILE_VERSION"


class InvalidProfileSelectionError(ProfileError):
    code = "INVALID_PROFILE_SELECTION"


class InvalidFieldValueError(ProfileError):
    code = "INVALID_FIELD_VALUE"


class CustomFieldConflictError(ProfileError):
    code = "CUSTOM_FIELD_CONFLICT"


class ExportCancelledError(ProfileError):
    code = "EXPORT_CANCELLED"


class ExportFailedError(ProfileError):
    code = "EXPORT_FAILED"


class DeleteFailedError(ProfileError):
    code = "DELETE_FAILED"


class DeletePartialError(ProfileError):
    code = "DELETE_PARTIAL"
