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
    CustomFieldConflictError,
    InvalidFieldValueError,
    InvalidProfileSelectionError,
    ProfileNotFoundError,
    StaleProfileVersionError,
)
from resume_agent.profile.export_service import export_profile_snapshot
from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldDefinition,
    FieldType,
    FieldValue,
    ProfileSnapshot,
    RepeatableRecord,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
    StandardFieldDefinition,
    is_contract_id,
)
from resume_agent.profile.policy import DEFAULT_POLICY, ConfirmationPolicy
from resume_agent.profile.standard_fields import standard_field_definitions
from resume_agent.profile.validation import validate_field_value
from resume_agent.storage.base import ProfileStore

Clock: TypeAlias = Callable[[], datetime]
Definition: TypeAlias = StandardFieldDefinition | CustomFieldDefinition
CatalogProvider: TypeAlias = Callable[[], Iterable[Definition]]
FieldInput: TypeAlias = FieldValue | Mapping[str, Any]
RecordInput: TypeAlias = RepeatableRecord | Mapping[str, Any]

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
        catalog: CatalogProvider | Iterable[Definition] = standard_field_definitions,
        policy: ConfirmationPolicy = DEFAULT_POLICY,
    ) -> None:
        self._store = store
        self._profile_id = profile_id
        self._clock = clock or _utc_now
        self._catalog = catalog
        self._policy = policy

    def _catalog_definitions(self) -> list[Definition]:
        provided = self._catalog() if callable(self._catalog) else self._catalog
        return [definition.model_copy(deep=True) for definition in provided]

    def _resolve_profile_id(self, profile_id: str | None) -> str:
        selected = profile_id if profile_id is not None else self._profile_id
        selected = selected if selected is not None else DEFAULT_PROFILE_ID
        if not is_contract_id(selected):
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
    def _validate_expected_profile_version(value: object) -> int:
        """Validate the integer revision required by the v0.1 lifecycle contract."""

        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InvalidFieldValueError(
                "profile version is invalid",
                details={"reason": "profile_version"},
            )
        return value

    @staticmethod
    def _mapping_value(data: Mapping[str, Any], name: str, default: Any = None) -> Any:
        if name in data:
            return data[name]
        if name == "id" and "field_id" in data:
            return data["field_id"]
        return default

    @staticmethod
    def _invalid(
        field_id: str | None, reason: str, field_type: FieldType | None = None
    ) -> InvalidFieldValueError:
        details: dict[str, Any] = {"reason": reason}
        if field_id:
            details["field_id"] = field_id
        if field_type is not None:
            details["field_type"] = field_type.value
        return InvalidFieldValueError("field value failed validation", details=details)

    def _definition_index(self) -> dict[str, FieldDefinition]:
        return {definition.id: definition for definition in self._catalog_definitions()}

    def _merged_definitions(self, current: ProfileSnapshot) -> list[Definition]:
        catalog = self._catalog_definitions()
        known = {item.id for item in catalog}
        return [
            *catalog,
            *(
                item.model_copy(deep=True)
                for item in current.field_definitions
                if item.is_custom and item.id not in known
            ),
        ]

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
        if not is_contract_id(field_id):
            raise self._invalid(None, "invalid_id")
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
            elif not is_contract_id(scope_context):
                raise self._invalid(field_id, "scope_context", definition.field_type)

            supplied_sensitivity = candidate_data.get("sensitivity", definition.default_sensitivity)
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

            requires_confirmation = (
                bool(candidate_data.get("requires_confirmation", False))
                or definition.requires_confirmation
                or sensitivity is not Sensitivity.NORMAL
            )
            source_data = candidate_data.get("source", {"kind": SourceKind.MANUAL.value})
            source = (
                source_data
                if isinstance(source_data, Source)
                else Source.model_validate(source_data)
            )
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

    def _normalise_fields(
        self, fields: Sequence[FieldInput], definitions: dict[str, FieldDefinition] | None = None
    ) -> tuple[list[FieldValue], datetime | None]:
        if not fields:
            raise self._invalid(None, "empty")
        definitions = definitions or self._definition_index()
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
        expected_profile_version = self._validate_expected_profile_version(expected_profile_version)
        if expected_profile_version != current.profile_version:
            raise StaleProfileVersionError(
                "profile version is stale",
                details={"expected": expected_profile_version, "actual": current.profile_version},
            )
        if not user_confirmed:
            raise ConfirmationRequiredError("explicit user confirmation is required")

        normalised, latest_input_timestamp = self._normalise_fields(
            fields, {item.id: item for item in self._merged_definitions(current)}
        )
        # This is intentionally called after parsing as well as before it: the
        # request-level flag gates all mutations, and policy can add field-level
        # requirements for custom/high-risk definitions.
        self._policy.check_mutation(user_confirmed=user_confirmed, fields=tuple(normalised))

        created_at, updated_at = self._timestamps(current, latest_input_timestamp)
        persisted_fields = [
            field.model_copy(update={"updated_at": updated_at}) for field in normalised
        ]

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
            field_definitions=self._merged_definitions(current),
            created_at=created_at,
            updated_at=updated_at,
        )
        # The store owns atomicity and encryption.  Do not catch its exceptions;
        # callers need the concrete storage error and the previous snapshot remains
        # authoritative when an implementation's write fails.
        self._store.write(next_snapshot)
        return self._copy_snapshot(next_snapshot)

    def _us2_context(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        user_confirmed: bool,
    ) -> tuple[str, ProfileSnapshot]:
        selected = self._resolve_profile_id(profile_id)
        current = self._read_current(selected)
        expected_profile_version = self._validate_expected_profile_version(expected_profile_version)
        if expected_profile_version != current.profile_version:
            raise StaleProfileVersionError(
                "profile version is stale",
                details={"expected": expected_profile_version, "actual": current.profile_version},
            )
        if not user_confirmed:
            raise ConfirmationRequiredError("explicit user confirmation is required")
        return selected, current

    def _us2_write(
        self,
        current: ProfileSnapshot,
        *,
        fields: Sequence[FieldValue] | None = None,
        records: Sequence[RepeatableRecord] | None = None,
        definitions: Sequence[Definition] | None = None,
        updated_at: datetime | None = None,
    ) -> ProfileSnapshot:
        timestamp = updated_at or self._safe_clock(_utc_now())
        next_fields = [
            item.model_copy(deep=True) for item in (current.fields if fields is None else fields)
        ]
        next_records = [
            item.model_copy(deep=True) for item in (current.records if records is None else records)
        ]
        next_definitions = [
            item.model_copy(deep=True)
            for item in (current.field_definitions if definitions is None else definitions)
        ]
        next_snapshot = ProfileSnapshot(
            profile_id=current.profile_id,
            profile_version=current.profile_version + 1,
            is_empty=not next_fields and not next_records,
            fields=next_fields,
            records=next_records,
            field_definitions=next_definitions,
            created_at=current.created_at,
            updated_at=timestamp,
        )
        self._store.write(next_snapshot)
        return self._copy_snapshot(next_snapshot)

    def _us2_definitions(self, current: ProfileSnapshot) -> dict[str, FieldDefinition]:
        definitions: dict[str, FieldDefinition] = {
            item.id: item for item in self._catalog_definitions()
        }
        definitions.update({item.id: item for item in current.field_definitions})
        return definitions

    def _us2_fields(
        self,
        fields: Sequence[FieldInput],
        definitions: dict[str, FieldDefinition],
    ) -> tuple[list[FieldValue], datetime | None]:
        if not fields:
            raise self._invalid(None, "empty")
        result: list[FieldValue] = []
        latest: datetime | None = None
        for raw in fields:
            value, supplied = self._normalise_input(raw, definitions)
            result.append(value)
            if supplied is not None and (latest is None or supplied > latest):
                latest = supplied
        return result, latest

    def _us2_record(
        self,
        raw: RecordInput,
        current: ProfileSnapshot,
    ) -> tuple[RepeatableRecord, datetime | None]:
        try:
            record = (
                raw if isinstance(raw, RepeatableRecord) else RepeatableRecord.model_validate(raw)
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise self._invalid(None, "record") from exc
        if record.confirmed is not True:
            raise ConfirmationRequiredError("record confirmation is required")
        if not is_contract_id(record.record_id):
            raise self._invalid(None, "record_id")
        fields, latest = self._us2_fields(record.fields, self._us2_definitions(current))
        timestamp = latest or record.updated_at
        return record.model_copy(
            update={"fields": fields, "confirmed": True, "updated_at": timestamp}
        ), latest

    def upsert_record(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        record: RecordInput,
        user_confirmed: bool,
    ) -> ProfileSnapshot:
        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        normalised, supplied_timestamp = self._us2_record(record, current)
        existing = next(
            (item for item in current.records if item.record_id == normalised.record_id), None
        )
        if existing is not None:
            normalised = normalised.model_copy(update={"created_at": existing.created_at})
        records = [item for item in current.records if item.record_id != normalised.record_id]
        records.append(normalised)
        records.sort(key=lambda item: (item.position, item.record_id))
        return self._us2_write(current, records=records, updated_at=supplied_timestamp)

    def delete_record(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        record_id: str,
        user_confirmed: bool,
    ) -> ProfileSnapshot:
        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        if not is_contract_id(record_id):
            raise self._invalid(None, "record_id")
        if not any(item.record_id == record_id for item in current.records):
            raise self._invalid(record_id, "unknown_record")
        records = [item for item in current.records if item.record_id != record_id]
        return self._us2_write(current, records=records)

    def reorder_records(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        ordered_record_ids: Sequence[str],
        user_confirmed: bool,
    ) -> ProfileSnapshot:
        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        requested = list(ordered_record_ids)
        actual = [item.record_id for item in current.records]
        if any(not is_contract_id(item) for item in requested):
            raise self._invalid(None, "record_order")
        if (
            any(not is_contract_id(item) for item in requested)
            or len(requested) != len(set(requested))
            or set(requested) != set(actual)
        ):
            raise self._invalid(None, "record_order")
        by_id = {item.record_id: item for item in current.records}
        records = [
            by_id[record_id].model_copy(update={"position": index})
            for index, record_id in enumerate(requested)
        ]
        return self._us2_write(current, records=records)

    def _validate_custom_definition(
        self,
        current: ProfileSnapshot,
        definition: CustomFieldDefinition,
    ) -> CustomFieldDefinition:
        from resume_agent.profile.errors import CustomFieldConflictError

        if not isinstance(definition, CustomFieldDefinition):
            raise self._invalid(None, "definition")
        if not is_contract_id(definition.id):
            raise self._invalid(None, "definition_id")
        standards = self._catalog_definitions()
        if any(item.id == definition.id for item in standards) or any(
            item.label.casefold() == definition.label.casefold() for item in standards
        ):
            raise CustomFieldConflictError("custom field conflicts with standard field")
        if any(item.id == definition.id for item in current.field_definitions):
            raise CustomFieldConflictError("custom field already exists")
        if definition.options:
            values = [option.value for option in definition.options]
            if len({repr(value) for value in values}) != len(values):
                raise self._invalid(definition.id, "duplicate_options")
        return definition.model_copy(update={"requires_confirmation": True})

    def create_custom_field(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        definition: CustomFieldDefinition,
        value: Any,
        scope: Scope,
        user_confirmed: bool,
        scope_context: str | None = None,
    ) -> ProfileSnapshot:
        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        definition = self._validate_custom_definition(current, definition)
        definitions = self._us2_definitions(current)
        definitions[definition.id] = definition
        candidate = {
            "id": definition.id,
            "value": value,
            "scope": scope,
            "scope_context": scope_context,
            "confirmed": True,
            "source": {"kind": SourceKind.MANUAL.value},
        }
        normalised, supplied_timestamp = self._normalise_input(candidate, definitions)
        timestamp = supplied_timestamp or self._safe_clock(_utc_now())
        persisted_definition = definition.model_copy(
            update={"created_at": definition.created_at or timestamp, "updated_at": timestamp}
        )
        fields = [
            *current.fields,
            normalised.model_copy(update={"updated_at": timestamp, "is_custom": True}),
        ]
        return self._us2_write(
            current,
            fields=fields,
            definitions=[*current.field_definitions, persisted_definition],
            updated_at=timestamp,
        )

    def update_custom_field(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        field_id: str,
        value: Any,
        user_confirmed: bool,
        scope: Scope | None = None,
        scope_context: str | None = None,
    ) -> ProfileSnapshot:
        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        definition = next(
            (item for item in current.field_definitions if item.id == field_id and item.is_custom),
            None,
        )
        if not isinstance(definition, CustomFieldDefinition):
            raise self._invalid(field_id, "unknown_custom_field")
        existing_values = [item for item in current.fields if item.id == field_id]
        existing_keys = {_field_key(item) for item in existing_values}
        if scope is None:
            if len(existing_keys) > 1:
                raise self._invalid(field_id, "ambiguous_scope")
            existing = existing_values[0] if existing_values else None
            chosen_scope = existing.scope if existing is not None else definition.allowed_scopes[0]
            chosen_context = (
                scope_context
                if scope_context is not None
                else (existing.scope_context if existing is not None else None)
            )
        else:
            chosen_scope = scope
            scoped_values = [item for item in existing_values if item.scope is scope]
            scoped_keys = {_field_key(item) for item in scoped_values}
            if scope_context is None and scope is not Scope.GLOBAL and len(scoped_keys) > 1:
                raise self._invalid(field_id, "ambiguous_scope_context")
            existing = scoped_values[0] if len(scoped_keys) == 1 else None
            if scope is Scope.GLOBAL:
                chosen_context = None
            elif scope_context is not None:
                chosen_context = scope_context
            elif existing is not None:
                chosen_context = existing.scope_context
            else:
                chosen_context = None
        candidate = {
            "id": field_id,
            "value": value,
            "scope": chosen_scope,
            "scope_context": chosen_context,
            "confirmed": True,
            "source": {"kind": SourceKind.MANUAL.value},
        }
        normalised, supplied_timestamp = self._normalise_input(
            candidate, self._us2_definitions(current)
        )
        timestamp = supplied_timestamp or self._safe_clock(_utc_now())
        target_key = _field_key(normalised)
        fields = [item for item in current.fields if _field_key(item) != target_key]
        fields.append(normalised.model_copy(update={"updated_at": timestamp, "is_custom": True}))
        definitions = [
            item.model_copy(update={"updated_at": timestamp}) if item.id == field_id else item
            for item in current.field_definitions
        ]
        return self._us2_write(
            current, fields=fields, definitions=definitions, updated_at=timestamp
        )

    def delete_custom_field(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        field_id: str,
        user_confirmed: bool,
    ) -> ProfileSnapshot:
        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        if not any(item.id == field_id and item.is_custom for item in current.field_definitions):
            raise self._invalid(field_id, "unknown_custom_field")
        return self._us2_write(
            current,
            fields=[item for item in current.fields if item.id != field_id],
            definitions=[item for item in current.field_definitions if item.id != field_id],
        )

    def upsert_extended(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        fields: Sequence[FieldInput] = (),
        records: Sequence[RecordInput] = (),
        custom_field_definitions: Sequence[CustomFieldDefinition] = (),
        delete_record_ids: Sequence[str] = (),
        delete_field_ids: Sequence[str] = (),
        delete_custom_field_definition_ids: Sequence[str] = (),
        record_order: Sequence[str] | None = None,
        user_confirmed: bool,
    ) -> ProfileSnapshot:
        """Apply one confirmed US2 bundle as a single optimistic write."""
        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        if not (
            fields
            or records
            or custom_field_definitions
            or delete_record_ids
            or delete_field_ids
            or delete_custom_field_definition_ids
            or record_order is not None
        ):
            raise self._invalid(None, "empty_bundle")
        definitions = self._us2_definitions(current)
        persisted_defs = [item.model_copy(deep=True) for item in current.field_definitions]
        new_definition_ids: set[str] = set()
        for raw_definition in custom_field_definitions:
            try:
                definition = (
                    raw_definition
                    if isinstance(raw_definition, CustomFieldDefinition)
                    else CustomFieldDefinition.model_validate(raw_definition)
                )
            except (ValidationError, TypeError, ValueError) as exc:
                raise self._invalid(None, "definition") from exc
            definition = self._validate_custom_definition(current, definition)
            if definition.id in definitions or any(
                item.label.casefold() == definition.label.casefold() for item in persisted_defs
            ):
                raise CustomFieldConflictError("custom field conflicts with an existing definition")
            new_definition_ids.add(definition.id)
            definitions[definition.id] = definition
            persisted_defs.append(definition)
        normalised_fields: list[FieldValue] = []
        latest: datetime | None = None
        for raw_field in fields:
            field, supplied = self._normalise_input(raw_field, definitions)
            normalised_fields.append(field)
            if supplied is not None and (latest is None or supplied > latest):
                latest = supplied
        # Include newly declared definitions while parsing records.
        staged = current.model_copy(update={"field_definitions": persisted_defs})
        normalised_records: list[RepeatableRecord] = []
        for raw_record in records:
            record, supplied = self._us2_record(raw_record, staged)
            normalised_records.append(record)
            if supplied is not None and (latest is None or supplied > latest):
                latest = supplied
        if delete_record_ids:
            if any(not is_contract_id(item) for item in delete_record_ids):
                raise self._invalid(None, "record_id")
            if len(delete_record_ids) != len(set(delete_record_ids)):
                raise self._invalid(None, "record_id")
        record_ids_input = [record.record_id for record in normalised_records]
        if any(not isinstance(item, str) or not item.strip() for item in record_ids_input):
            raise self._invalid(None, "record_id")
        if len(record_ids_input) != len(set(record_ids_input)):
            raise self._invalid(None, "duplicate_record_id")
        if delete_record_ids and any(
            record_id in set(delete_record_ids)
            for record_id in record_ids_input
            if isinstance(record_id, str)
        ):
            raise self._invalid(None, "record_delete_conflict")
        fields_out = [item.model_copy(deep=True) for item in current.fields]
        for field in normalised_fields:
            fields_out = [
                item
                for item in fields_out
                if not (
                    item.id == field.id
                    and item.scope == field.scope
                    and item.scope_context == field.scope_context
                )
            ]
            fields_out.append(field)
        if delete_field_ids:
            if any(not is_contract_id(item) for item in delete_field_ids):
                raise self._invalid(None, "field_id")
            field_ids = set(delete_field_ids)
            fields_out = [item for item in fields_out if item.id not in field_ids]

        records_out = [
            item
            for item in current.records
            if item.record_id not in {record.record_id for record in normalised_records}
        ]
        records_out.extend(normalised_records)
        if record_order is not None:
            requested = list(record_order)
            if any(not is_contract_id(item) for item in requested):
                raise self._invalid(None, "record_order")
            if len(requested) != len(set(requested)):
                raise self._invalid(None, "record_order")
            actual = [item.record_id for item in records_out]
            if len(requested) != len(set(requested)) or set(requested) != set(actual):
                raise self._invalid(None, "record_order")
            by_id = {item.record_id: item for item in records_out}
            records_out = [
                by_id[record_id].model_copy(update={"position": index})
                for index, record_id in enumerate(requested)
            ]
        if delete_record_ids:
            if any(not is_contract_id(item) for item in delete_record_ids):
                raise self._invalid(None, "record_id")
            delete_records = set(delete_record_ids)
            if not delete_records.issubset({item.record_id for item in records_out}):
                raise self._invalid(None, "unknown_record")
            records_out = [item for item in records_out if item.record_id not in delete_records]
        if delete_custom_field_definition_ids:
            if any(not is_contract_id(item) for item in delete_custom_field_definition_ids):
                raise self._invalid(None, "custom_field_id")
            if len(delete_custom_field_definition_ids) != len(
                set(delete_custom_field_definition_ids)
            ):
                raise self._invalid(None, "custom_field_id")
        if delete_custom_field_definition_ids:
            delete_ids = set(delete_custom_field_definition_ids)
            standard_ids = {item.id for item in self._catalog_definitions()}
            if delete_ids & standard_ids:
                raise CustomFieldConflictError("standard field definitions cannot be deleted")
            if delete_ids & new_definition_ids:
                raise CustomFieldConflictError("cannot add and delete the same custom definition")
            existing_custom_ids = {item.id for item in persisted_defs if item.is_custom}
            if not delete_ids.issubset(existing_custom_ids):
                raise self._invalid(None, "unknown_custom_field")
            persisted_defs = [item for item in persisted_defs if item.id not in delete_ids]
            fields_out = [item for item in fields_out if item.id not in delete_ids]
            records_out = [
                record.model_copy(
                    update={
                        "fields": [field for field in record.fields if field.id not in delete_ids]
                    }
                )
                for record in records_out
            ]
        # Drop records that would become invalid confirmed-empty records.
        records_out = [record for record in records_out if record.fields]
        records_out = [
            record.model_copy(update={"position": index})
            for index, record in enumerate(
                sorted(records_out, key=lambda item: (item.position, item.record_id))
            )
        ]
        return self._us2_write(
            current,
            fields=fields_out,
            records=records_out,
            definitions=persisted_defs,
            updated_at=latest,
        )

    @staticmethod
    def _validate_delete_selection(selection: Mapping[str, Any]) -> tuple[str, Any]:
        if not isinstance(selection, Mapping):
            raise InvalidProfileSelectionError("delete selection is invalid")
        allowed = {"field_ids", "record_ids", "custom_field_definition_ids", "delete_all"}
        if set(selection) - allowed:
            raise InvalidProfileSelectionError("delete selection is invalid")
        present = [key for key in allowed if key in selection]
        if len(present) != 1:
            raise InvalidProfileSelectionError("delete selection is ambiguous")
        kind = present[0]
        value = selection[kind]
        if kind == "delete_all":
            if value is not True:
                raise InvalidProfileSelectionError("delete_all must be true")
            return kind, value
        if not isinstance(value, list) or not value:
            raise InvalidProfileSelectionError("delete selection is empty")
        if any(not is_contract_id(item) for item in value):
            raise InvalidProfileSelectionError("delete selection contains invalid ids")
        if len(value) != len(set(value)):
            raise InvalidProfileSelectionError("delete selection contains duplicate ids")
        return kind, value

    def _delete_all(self, current: ProfileSnapshot, *, selected: str) -> dict[str, Any]:
        deleted_field_ids = list(dict.fromkeys(field.id for field in current.fields))
        deleted_record_ids = [record.record_id for record in current.records]
        deleted_definition_ids = [
            definition.id for definition in current.field_definitions if definition.is_custom
        ]
        cleanup_pending: list[str] = []
        warnings: list[dict[str, str]] = []
        file_deleted = False
        try:
            self._store.delete()
            file_deleted = True
        except Exception:  # noqa: BLE001 - cleanup must report partial failure
            cleanup_pending.append("encrypted_snapshot")
            warnings.append(
                {
                    "code": "ENCRYPTED_SNAPSHOT_DELETE_FAILED",
                    "message": "加密资料文件未能删除，请重试或手动处理。",
                    "severity": "error",
                }
            )
        provider = getattr(self._store, "key_provider", None)
        if file_deleted:
            if provider is not None and callable(getattr(provider, "destroy_key", None)):
                try:
                    provider.destroy_key()
                except Exception:  # noqa: BLE001 - cleanup must report partial failure
                    cleanup_pending.append("key_reference")
                    warnings.append(
                        {
                            "code": "KEY_REFERENCE_DELETE_FAILED",
                            "message": "本地密钥引用未能清理，请重试。",
                            "severity": "error",
                        }
                    )
            elif provider is not None:
                cleanup_pending.append("key_reference")
                warnings.append(
                    {
                        "code": "KEY_REFERENCE_DELETE_FAILED",
                        "message": "本地密钥引用未能清理，请重试。",
                        "severity": "error",
                    }
                )
        elif provider is not None:
            cleanup_pending.append("key_reference")
        task_state = "partial" if cleanup_pending else "completed"
        return {
            "profile_id": current.profile_id,
            "profile_version": 0 if file_deleted else current.profile_version,
            "task_state": task_state,
            "deleted_field_ids": deleted_field_ids,
            "deleted_record_ids": deleted_record_ids,
            "deleted_custom_field_definition_ids": deleted_definition_ids,
            "all_data_deleted": task_state == "completed",
            "cleanup_pending": cleanup_pending,
            "warnings": warnings,
        }

    def delete(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        selection: Mapping[str, Any],
        user_confirmed: bool,
    ) -> dict[str, Any]:
        """Delete selected values or the complete local profile after confirmation."""

        selected, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        kind, value = self._validate_delete_selection(selection)
        if kind == "delete_all":
            return self._delete_all(current, selected=selected)

        ids = set(value)
        fields_before = list(current.fields)
        records_before = list(current.records)
        definitions_before = list(current.field_definitions)
        fields = [field for field in fields_before if field.id not in ids]
        definitions = definitions_before
        records: list[RepeatableRecord] = []
        deleted_record_ids: list[str] = []
        if kind == "record_ids":
            records = [record for record in records_before if record.record_id not in ids]
            deleted_record_ids = [
                record.record_id for record in records_before if record.record_id in ids
            ]
        else:
            for record in records_before:
                filtered = [field for field in record.fields if field.id not in ids]
                if filtered:
                    records.append(record.model_copy(update={"fields": filtered}))
                else:
                    records.append(record)
        deleted_field_ids: list[str] = []
        deleted_definition_ids: list[str] = []
        if kind == "field_ids":
            deleted_field_ids = [
                field_id
                for field_id in value
                if any(field.id == field_id for field in fields_before)
                or any(field.id == field_id for record in records_before for field in record.fields)
            ]
        elif kind == "custom_field_definition_ids":
            standard_ids = {definition.id for definition in self._catalog_definitions()}
            if ids & standard_ids:
                raise InvalidProfileSelectionError("standard field definitions cannot be deleted")
            existing_custom = {
                definition.id for definition in definitions_before if definition.is_custom
            }
            deleted_definition_ids = [field_id for field_id in value if field_id in existing_custom]
            fields = [field for field in fields_before if field.id not in ids]
            records = [
                record.model_copy(
                    update={"fields": [field for field in record.fields if field.id not in ids]}
                )
                for record in records_before
            ]
            definitions = [
                definition for definition in definitions_before if definition.id not in ids
            ]
        else:
            definitions = definitions_before
        records = [record for record in records if record.fields]
        records = [
            record.model_copy(update={"position": position})
            for position, record in enumerate(
                sorted(records, key=lambda item: (item.position, item.record_id))
            )
        ]
        changed = (
            fields != fields_before
            or records != records_before
            or definitions != definitions_before
        )
        if not changed:
            return {
                "profile_id": selected,
                "profile_version": current.profile_version,
                "task_state": "completed",
                "deleted_field_ids": deleted_field_ids,
                "deleted_record_ids": deleted_record_ids,
                "deleted_custom_field_definition_ids": deleted_definition_ids,
                "all_data_deleted": False,
                "cleanup_pending": [],
                "warnings": [],
            }
        snapshot = self._us2_write(
            current,
            fields=fields,
            records=records,
            definitions=definitions,
        )
        return {
            "profile_id": snapshot.profile_id,
            "profile_version": snapshot.profile_version,
            "task_state": "completed",
            "deleted_field_ids": deleted_field_ids,
            "deleted_record_ids": deleted_record_ids,
            "deleted_custom_field_definition_ids": deleted_definition_ids,
            "all_data_deleted": False,
            "cleanup_pending": [],
            "warnings": [],
        }

    def export(
        self,
        profile_id: str | None,
        *,
        expected_profile_version: int,
        selection: Mapping[str, Any],
        destination: Any,
        user_confirmed: bool,
        overwrite_existing: bool = False,
        overwrite_confirmed: bool = False,
    ) -> dict[str, Any]:
        """Export a selected local copy without changing the profile snapshot."""

        _, current = self._us2_context(
            profile_id,
            expected_profile_version=expected_profile_version,
            user_confirmed=user_confirmed,
        )
        return export_profile_snapshot(
            current,
            selection=selection,
            destination=destination,
            overwrite_existing=overwrite_existing,
            overwrite_confirmed=overwrite_confirmed,
        )

    def cancel(self, profile_id: str | None = None) -> ProfileSnapshot:
        """Discard an in-memory edit by simply returning the persisted snapshot."""

        return self.read(profile_id)


__all__ = ["Clock", "FieldInput", "ProfileService"]
