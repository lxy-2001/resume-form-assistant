"""Confirmation policy for local profile mutations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from resume_agent.profile.errors import ConfirmationRequiredError
from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldDefinition,
    FieldValue,
    Sensitivity,
)


@dataclass(frozen=True, slots=True)
class ConfirmationPolicy:
    """Centralize confirmation decisions without any model or network dependency."""

    additional_field_ids: frozenset[str] = field(default_factory=frozenset)

    def requires_field_confirmation(self, item: FieldDefinition | FieldValue | Any) -> bool:
        field_id = getattr(item, "id", None)
        if field_id in self.additional_field_ids:
            return True
        if isinstance(item, CustomFieldDefinition) or bool(getattr(item, "is_custom", False)):
            return True
        sensitivity = getattr(item, "sensitivity", getattr(item, "default_sensitivity", None))
        if sensitivity in {Sensitivity.SENSITIVE, Sensitivity.HIGHLY_SENSITIVE}:
            return True
        return bool(getattr(item, "requires_confirmation", False))

    def check_mutation(
        self,
        *,
        user_confirmed: bool,
        fields: list[FieldDefinition | FieldValue] | tuple[FieldDefinition | FieldValue, ...] = (),
    ) -> None:
        """Reject any mutation lacking the explicit user confirmation envelope."""

        if not user_confirmed:
            raise ConfirmationRequiredError("explicit user confirmation is required")
        for item in fields:
            if self.requires_field_confirmation(item) and not bool(getattr(item, "confirmed", True)):
                raise ConfirmationRequiredError("field confirmation is required")

    def require(self, user_confirmed: bool, item: FieldDefinition | FieldValue | None = None) -> None:
        if not user_confirmed or (item is not None and self.requires_field_confirmation(item) and not bool(getattr(item, "confirmed", True))):
            raise ConfirmationRequiredError("explicit user confirmation is required")


DEFAULT_POLICY = ConfirmationPolicy()


__all__ = ["DEFAULT_POLICY", "ConfirmationPolicy"]
