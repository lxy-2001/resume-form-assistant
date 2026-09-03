"""Application service for the local profile library.

The service is deliberately independent from HTTP, the browser extension and the
concrete encrypted store.  It validates and normalises a complete mutation before
calling the injected :class:`~resume_agent.storage.base.ProfileStore` exactly once.
That boundary makes failed validation and stale requests non-mutating while keeping
storage failures visible to the caller.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, TypeAlias

from pydantic import ValidationError

from resume_agent.profile.errors import (
    ConfirmationRequiredError,
    InvalidFieldValueError,
    ProfileNotFoundError,
    StaleProfileVersionError,
)
from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldDefinition,
    FieldType,
    FieldValue,
    ProfileSnapshot,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
)
from resume_agent.profile.policy import DEFAULT_POLICY, ConfirmationPolicy
from resume_agent.profile.standard_fields import standard_field_definitions
from resume_agent.profile.validation import validate_field_value
from resume_agent.storage.base import ProfileStore

Clock: TypeAlias = Callable[[], datetime]
CatalogProvider: TypeAlias = Callable[[], Iterable[FieldDefinition]]
FieldInput: TypeAlias = FieldValue | Mapping[str, Any]

DEFAULT_PROFILE_ID = "default-profile"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _field_key(field: FieldValue) -> tuple[str, Scope, str | None]:
    """Return the identity used for merging one current field value."""

    return field.id, field.scope, field.scope_context


class ProfileService:
    """Coordinate confirmed profile mutations behind a ``ProfileStore`` seam.

    ``fields`` accepted by :meth:`upsert` are either ``FieldValue`` instances or
    mappings with a canonical ``id`` (``field_id`` is accepted as a compatibility
    alias) and ``value``.  Other metadata may be omitted for standard fields and is
    filled from the injected catalog.  If supplied, ``confirmed`` must be true and
    ``source.kind`` must be ``manual``; the request-level ``user_confirmed`` flag is
    always required as well.

    ``profile_id`` is optional so a caller can use one service for a selected local
    profile.  Supplying it at construction fixes the service to that identity and
    prevents accidental cross-profile reads or writes.
    """

    def __init__(
        self,
        store: ProfileStore,
        *,
        profile_id: str | None = None,
        clock: Clock | None = None,
        catalog: CatalogProvider | Iterable[FieldDefinition] = standard_field_definitions,
        policy: ConfirmationPolicy = DEFAULT_POLICY,
    ) -> None:
        self._store = store
        self._profile_id = profile_id
        self._clock = clock or _utc_now
        self._catalog = catalog
        self._policy = policy

    def _catalog_definitions(self) -> list[FieldDefinition]:
        provided = self._catalog() if callable(self._catalog) else self._catalog
        return [definition.model_copy(deep=True) for definition in provided]

    def _resolve_profile_id(self, profile_id: str | None) -> str:
        selected = profile_id or self._profile_id or DEFAULT_PROFILE_ID
        if not isinstance(selected, str) or not selected.strip() or len(selected) > 128:
            raise ProfileNotFoundError("profile was not found")
        if self._profile_id is not None and selected != self._profile_id:
            raise ProfileNotFoundError("profile was not found")
        return selected

    @staticmethod
    def _copy_snapshot(snapshot: ProfileSnapshot) -> ProfileSnapshot:
        return snapshot.model_copy(deep=True)

    def _empty_snapshot(self, profile_id: str) -> ProfileSnapshot:
        timestamp = self._safe_clock(_utc_now())
        return ProfileSnapshot(
            profile_id=profile_id,
            profile_version=0,
            is_empty=True,
            fields=[],
            records=[],
            field_definitions=self._catalog_definitions(),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def _read_current(self, profile_id: str) -> ProfileSnapshot:
        stored = self._store.read()
        if stored is None:
            return self._empty_snapshot(profile_id)
        try:
            snapshot = (
                stored
                if isinstance(stored, ProfileSnapshot)
                else ProfileSnapshot.model_validate(stored)
            )
        except (ValidationError, TypeError, ValueError) as exc:
            # A malformed persisted value is a storage concern in concrete stores;
            # do not expose Pydantic internals or the stored contents here.
            raise InvalidFieldValueError(
                "stored profile snapshot is invalid", details={"reason": "snapshot"}
            ) from exc
        if snapshot.profile_id != profile_id:
            raise ProfileNotFoundError("profile was not found")
        if not snapshot.field_definitions:
            snapshot = snapshot.model_copy(
                update={"field_definitions": self._catalog_definitions()}
            )
        return self._copy_snapshot(snapshot)

    def read(self, profile_id: str | None = None) -> ProfileSnapshot:
        """Read a deep copy of the current snapshot without writing an empty state."""

        selected = self._resolve_profile_id(profile_id)
        return self._read_current(selected)

    def _safe_clock(self, fallback: datetime) -> datetime:
        """Call the injected clock, tolerating finite test clocks gracefully."""

        try:
            value = self._clock()
        except StopIteration:
            return fallback
        if not isinstance(value, datetime):
            return fallback
        return value

    @staticmethod
    def _mapping_value(data: Mapping[str, Any], name: str, default: Any = None) -> Any:
        if name in data:
            return data[name]
        if name == "id" and "field_id" in data:
            return data["field_id"]
        return default

    @staticmethod
    def _invalid(field_id: str | None, reason: str, field_type: FieldType | None = None) -> InvalidFieldValueError:
        details: dict[str, Any] = {"reason": reason}
        if field_id:
            details["field_id"] = field_id
        if field_type is not None:
            details["field_type"] = field_type.value
        return InvalidFieldValueError("field value failed validation", details=details)

    def _definition_index(self) -> dict[str, FieldDefinition]:
        return {definition.id: definition for definition in self._catalog_definitions()}

    def _normalise_input(
        self,
        raw: FieldInput,
        definitions: dict[str, FieldDefinition],
    ) -> tuple[FieldValue, datetime | None]:
        """Parse one candidate and return it with its caller timestamp if present."""

        if isinstance(raw, FieldValue):
            candidate_data: Mapping[str, Any] = raw.to_dict()
        elif isinstance(raw, Mapping):
            candidate_data = raw
        else:
            raise self._invalid(None, "type")

        raw_id = self._mapping_value(candidate_data, "id")
        field_id = raw_id if isinstance(raw_id, str) else None
        if field_id is None or not field_id.strip():
            raise self._invalid(None, "missing_id")
        definition = definitions.get(field_id)
        if definition is None:
            raise self._invalid(field_id, "unknown_field")

        # A false explicit confirmation is rejected before Pydantic validation,
        # because FieldValue intentionally cannot represent unconfirmed persisted data.
        if "confirmed" in candidate_data and candidate_data["confirmed"] is not True:
            raise ConfirmationRequiredError("field confirmation is required")

        raw_value = self._mapping_value(candidate_data, "value")
        if "value" not in candidate_data:
            raise self._invalid(field_id, "missing_value", definition.field_type)

        try:
            supplied_type = candidate_data.get("field_type")
            if supplied_type is not None and FieldType(supplied_type) is not definition.field_type:
                raise self._invalid(field_id, "field_type", definition.field_type)

            supplied_scope = candidate_data.get("scope", definition.allowed_scopes[0])
            scope = supplied_scope if isinstance(supplied_scope, Scope) else Scope(supplied_scope)
            if scope not in definition.allowed_scopes:
                raise self._invalid(field_id, "scope", definition.field_type)

            scope_context = candidate_data.get("scope_context")
            if scope is Scope.GLOBAL:
                scope_context = None
            elif not isinstance(scope_context, str) or not scope_context.strip():
                raise self._invalid(field_id, "scope_context", definition.field_type)

            supplied_sensitivity = candidate_data.get(
                "sensitivity", definition.default_sensitivity
            )
            sensitivity = (
                supplied_sensitivity
                if isinstance(supplied_sensitivity, Sensitivity)
                else Sensitivity(supplied_sensitivity)
            )
            # Callers may make a value more sensitive, but never downgrade a
            # product-defined high-risk field.
            levels = {
                Sensitivity.NORMAL: 0,
                Sensitivity.SENSITIVE: 1,
                Sensitivity.HIGHLY_SENSITIVE: 2,
            }
            if levels[sensitivity] < levels[definition.default_sensitivity]:
                raise self._invalid(field_id, "sensitivity", definition.field_type)

            requires_confirmation = bool(
                candidate_data.get("requires_confirmation", False)
            ) or definition.requires_confirmation or sensitivity is not Sensitivity.NORMAL
            source_data = candidate_data.get("source", {"kind": SourceKind.MANUAL.value})
            source = source_data if isinstance(source_data, Source) else Source.model_validate(source_data)
            if source.kind is not SourceKind.MANUAL:
                raise self._invalid(field_id, "source", definition.field_type)

            supplied_timestamp = candidate_data.get("updated_at")
            caller_timestamp = (
                supplied_timestamp if isinstance(supplied_timestamp, datetime) else None
            )
            # Build a confirmed provisional value so the deterministic validator
            # can normalise the candidate before any snapshot or store mutation.
            provisional = FieldValue(
                id=field_id,
                label=definition.label,
                field_type=definition.field_type,
                value=raw_value,
                scope=scope,
                scope_context=scope_context,
                sensitivity=sensitivity,
                requires_confirmation=requires_confirmation,
                confirmed=True,
                source=source,
                updated_at=caller_timestamp or _utc_now(),
                is_custom=isinstance(definition, CustomFieldDefinition),
                aliases=definition.aliases,
                options=definition.options,
                validation=definition.validation,
            )
            normalised = validate_field_value(provisional, definition)
        except ConfirmationRequiredError:
            raise
        except InvalidFieldValueError:
            raise
        except (ValidationError, TypeError, ValueError) as exc:
            raise self._invalid(field_id, "metadata", definition.field_type) from exc
        return normalised, caller_timestamp

    def _normalise_fields(self, fields: Sequence[FieldInput]) -> tuple[list[FieldValue], datetime | None]:
        if not fields:
            raise self._invalid(None, "empty")
        definitions = self._definition_index()
        result: list[FieldValue] = []
        latest_input_timestamp: datetime | None = None
        for raw in fields:
            value, supplied_timestamp = self._normalise_input(raw, definitions)
            result.append(value)
            if supplied_timestamp is not None and (
                latest_input_timestamp is None or supplied_timestamp > latest_input_timestamp
            ):
                latest_input_timestamp = supplied_timestamp
        return result, latest_input_timestamp

    def _timestamps(
        self,
        current: ProfileSnapshot,
        latest_input_timestamp: datetime | None,
    ) -> tuple[datetime, datetime]:
        fallback = latest_input_timestamp or current.updated_at or _utc_now()
        if current.profile_version == 0 and current.is_empty:
            created_at = self._safe_clock(fallback)
            updated_at = self._safe_clock(created_at)
            return created_at, updated_at
        return current.created_at, self._safe_clock(fallback)

    def upsert(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        fields: Sequence[FieldInput],
        user_confirmed: bool,
    ) -> ProfileSnapshot:
        """Validate, merge and persist confirmed field values in one write."""

        selected = self._resolve_profile_id(profile_id)
        current = self._read_current(selected)
        if (
            isinstance(expected_profile_version, bool)
            or not isinstance(expected_profile_version, int)
            or expected_profile_version != current.profile_version
        ):
            raise StaleProfileVersionError(
                "profile version is stale",
                details={"expected": expected_profile_version, "actual": current.profile_version},
            )
        if not user_confirmed:
            raise ConfirmationRequiredError("explicit user confirmation is required")

        normalised, latest_input_timestamp = self._normalise_fields(fields)
        # This is intentionally called after parsing as well as before it: the
        # request-level flag gates all mutations, and policy can add field-level
        # requirements for custom/high-risk definitions.
        self._policy.check_mutation(user_confirmed=user_confirmed, fields=tuple(normalised))

        created_at, updated_at = self._timestamps(current, latest_input_timestamp)
        persisted_fields = [field.model_copy(update={"updated_at": updated_at}) for field in normalised]

        merged = [field.model_copy(deep=True) for field in current.fields]
        positions = {_field_key(field): index for index, field in enumerate(merged)}
        for field in persisted_fields:
            key = _field_key(field)
            existing_index = positions.get(key)
            if existing_index is None:
                positions[key] = len(merged)
                merged.append(field)
            else:
                merged[existing_index] = field

        next_snapshot = ProfileSnapshot(
            profile_id=selected,
            profile_version=current.profile_version + 1,
            is_empty=not merged and not current.records,
            fields=merged,
            records=[record.model_copy(deep=True) for record in current.records],
            field_definitions=self._catalog_definitions()
            or [definition.model_copy(deep=True) for definition in current.field_definitions],
            created_at=created_at,
            updated_at=updated_at,
        )
        # The store owns atomicity and encryption.  Do not catch its exceptions;
        # callers need the concrete storage error and the previous snapshot remains
        # authoritative when an implementation's write fails.
        self._store.write(next_snapshot)
        return self._copy_snapshot(next_snapshot)

    def cancel(self, profile_id: str | None = None) -> ProfileSnapshot:
        """Discard an in-memory edit by simply returning the persisted snapshot."""

        return self.read(profile_id)


__all__ = ["Clock", "FieldInput", "ProfileService"]
