"""Profile lifecycle HTTP routes for the F001 local profile library."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from copy import deepcopy
from functools import wraps
from threading import RLock
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from resume_agent.api.app import SCHEMA_VERSION, _error_payload
from resume_agent.profile.errors import (
    ExportFailedError,
    InvalidProfileSelectionError,
    LifecycleError,
)
from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldValue,
    RepeatableRecord,
    Scope,
    is_contract_id,
)
from resume_agent.profile.service import ProfileService

_READ_KEYS = {"schema_version", "request_id", "task_id", "operation", "profile_id"}
_UPSERT_KEYS = _READ_KEYS | {
    "expected_profile_version",
    "user_confirmed",
    "mode",
    "fields",
    "records",
    "custom_field_definitions",
    "delete_record_ids",
    "delete_custom_field_definition_ids",
    "record_order",
    "delete_field_ids",
}
_DELETE_KEYS = _READ_KEYS | {
    "expected_profile_version",
    "user_confirmed",
    "selection",
}
_EXPORT_KEYS = _READ_KEYS | {
    "expected_profile_version",
    "user_confirmed",
    "selection",
    "format",
    "destination",
}

# The domain service accepts a compact partial field mapping for internal callers
# (metadata can be filled from the standard catalog). The HTTP boundary requires
# the complete v0.1 wire shape and rejects unknown JSON members. These sets mirror
# ProfileField, ProfileRecord, ProfileFieldDefinition and their nested objects.
_FIELD_KEYS = {
    "id",
    "label",
    "field_type",
    "value",
    "scope",
    "scope_context",
    "sensitivity",
    "requires_confirmation",
    "confirmed",
    "source",
    "updated_at",
    "is_custom",
    "aliases",
    "options",
    "validation",
}
_FIELD_REQUIRED_KEYS = {
    "id",
    "label",
    "field_type",
    "value",
    "scope",
    "sensitivity",
    "requires_confirmation",
    "confirmed",
    "source",
    "updated_at",
}
_SOURCE_KEYS = {"kind", "profile_field_id", "document_ref", "location", "detail"}
_SOURCE_REQUIRED_KEYS = {"kind"}
_OPTION_KEYS = {"value", "label", "selected", "disabled"}
_OPTION_REQUIRED_KEYS = {"value", "label"}
_VALIDATION_KEYS = {
    "format",
    "pattern",
    "min_length",
    "max_length",
    "minimum",
    "maximum",
    "allowed_values",
}
_RECORD_KEYS = {
    "record_id",
    "record_type",
    "position",
    "fields",
    "confirmed",
    "created_at",
    "updated_at",
}
_RECORD_REQUIRED_KEYS = {
    "record_id",
    "record_type",
    "position",
    "fields",
    "confirmed",
    "created_at",
    "updated_at",
}
_DEFINITION_KEYS = {
    "id",
    "label",
    "field_type",
    "default_sensitivity",
    "requires_confirmation",
    "is_custom",
    "allowed_scopes",
    "aliases",
    "options",
    "validation",
    "created_at",
    "updated_at",
}
_DEFINITION_REQUIRED_KEYS = {
    "id",
    "label",
    "field_type",
    "default_sensitivity",
    "requires_confirmation",
    "is_custom",
    "allowed_scopes",
}
_FIELD_SELECTOR_KEYS = {"id", "scope", "scope_context"}


class _RequestReplayCache:
    """Keep metadata-only successful mutation responses for request retries.

    The cache stores a digest of the request body rather than the body itself, so
    sensitive field values are not retained by the idempotency layer.  It is
    intentionally process-local for the single-user local service; a retry after
    a process restart is still protected by the optimistic profile version.
    """

    def __init__(self, max_entries: int = 256) -> None:
        self._max_entries = max_entries
        self._entries: dict[str, tuple[str, dict[str, Any]]] = {}
        self._lock = RLock()
        # Mutations are serialized in this process. The second replay lookup
        # performed under this lock closes the check-then-write race for two
        # concurrent retries carrying the same request_id.
        self._mutation_lock = RLock()

    @staticmethod
    def _fingerprint(body: Mapping[str, Any]) -> str:
        # request_id names the logical operation and task_id is only a
        # correlation label; neither should make an otherwise identical retry
        # look like a different mutation.
        operation_body = {
            key: value for key, value in body.items() if key not in {"request_id", "task_id"}
        }
        canonical = json.dumps(
            operation_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def lookup(
        self, request_id: str, body: Mapping[str, Any]
    ) -> tuple[dict[str, Any] | None, bool]:
        fingerprint = self._fingerprint(body)
        with self._lock:
            entry = self._entries.get(request_id)
            if entry is None:
                return None, False
            if entry[0] != fingerprint:
                return None, True
            return deepcopy(entry[1]), False

    def remember(self, request_id: str, body: Mapping[str, Any], payload: dict[str, Any]) -> None:
        fingerprint = self._fingerprint(body)
        with self._lock:
            if request_id not in self._entries and len(self._entries) >= self._max_entries:
                self._entries.pop(next(iter(self._entries)))
            self._entries[request_id] = (fingerprint, deepcopy(payload))


def _serialized_mutation(cache: _RequestReplayCache) -> Any:
    """Serialize one mutation handler around replay lookup and persistence.

    The service is deliberately single-process in v0.1. Holding this lock for
    the handler means a second request with the same request_id observes the
    first response after it commits instead of executing a second write.
    """

    def decorate(handler: Any) -> Any:
        @wraps(handler)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            with cache._mutation_lock:
                return await handler(*args, **kwargs)

        return wrapped

    return decorate


def _replay_response(
    request: Request, body: Mapping[str, Any], cache: _RequestReplayCache
) -> JSONResponse | None:
    request_id, task_id = _identifiers(request, body)
    replay, conflict = cache.lookup(request_id, body)
    if conflict:
        return _bad_request(
            request,
            "request_id cannot be reused for a different operation",
            request_id=request_id,
            task_id=task_id,
            code="INVALID_FIELD_VALUE",
        )
    if replay is not None:
        return JSONResponse(replay)
    return None


def _identifiers(request: Request, body: Mapping[str, Any]) -> tuple[str, str]:
    body_request_id = body.get("request_id")
    body_task_id = body.get("task_id")
    header_request_id = request.headers.get("x-request-id")
    header_task_id = request.headers.get("x-task-id")
    request_id = (
        body_request_id
        if is_contract_id(body_request_id)
        else header_request_id
        if is_contract_id(header_request_id)
        else "local-request"
    )
    task_id = (
        body_task_id
        if is_contract_id(body_task_id)
        else header_task_id
        if is_contract_id(header_task_id)
        else "local-task"
    )
    return str(request_id), str(task_id)


def _bad_request(
    request: Request,
    message: str,
    *,
    request_id: str | None = None,
    task_id: str | None = None,
    code: str = "INVALID_FIELD_VALUE",
) -> JSONResponse:
    payload = _error_payload(
        request,
        code=code,
        message=message,
        retryable=False,
    )
    if request_id:
        payload["request_id"] = request_id
    if task_id:
        payload["task_id"] = task_id
    return JSONResponse(payload, status_code=400)


def _string_id_list(value: object, *, allow_empty: bool = True) -> bool:
    """Validate an ID-array shape before it reaches set()/dict() operations."""

    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    try:
        unique = len(value) == len(set(value))
    except TypeError:
        return False
    return unique and all(is_contract_id(item) for item in value)


def _mapping_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, Mapping) for item in value)


def _nested_members_valid(value: Mapping[str, Any], allowed: set[str]) -> bool:
    return not (set(value) - allowed)


def _options_valid(value: object) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if (
            not isinstance(item, Mapping)
            or not _nested_members_valid(item, _OPTION_KEYS)
            or not _OPTION_REQUIRED_KEYS <= set(item)
            or not isinstance(item.get("label"), str)
            or not item.get("label", "").strip()
        ):
            return False
        if "selected" in item and not isinstance(item["selected"], bool):
            return False
        if "disabled" in item and not isinstance(item["disabled"], bool):
            return False
    return True


def _validation_valid(value: object) -> bool:
    if not isinstance(value, Mapping) or not _nested_members_valid(value, _VALIDATION_KEYS):
        return False
    if "format" in value:
        format_value = value["format"]
        if not isinstance(format_value, str) or format_value not in {
            "email",
            "phone",
            "date",
            "year",
            "url",
            "postal_code",
        }:
            return False
    if "pattern" in value and not isinstance(value["pattern"], str):
        return False
    for key in ("min_length", "max_length"):
        if key in value and (
            isinstance(value[key], bool) or not isinstance(value[key], int) or value[key] < 0
        ):
            return False
    for key in ("minimum", "maximum"):
        if key in value and (
            isinstance(value[key], bool)
            or not isinstance(value[key], (int, float))
            or (isinstance(value[key], float) and not math.isfinite(value[key]))
        ):
            return False
    return "allowed_values" not in value or isinstance(value["allowed_values"], list)


def _source_valid(value: object) -> bool:
    if not isinstance(value, Mapping) or not _nested_members_valid(value, _SOURCE_KEYS):
        return False
    kind = value.get("kind")
    if (
        _SOURCE_REQUIRED_KEYS - set(value)
        or not isinstance(kind, str)
        or kind
        not in {
            "manual",
            "import",
            "rule",
            "agent",
            "user_correction",
            "website_config",
        }
    ):
        return False
    for key in ("profile_field_id", "document_ref"):
        if key in value and not is_contract_id(value[key]):
            return False
    for key in ("location", "detail"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            return False
    return True


def _field_mapping_valid(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    if not _nested_members_valid(value, _FIELD_KEYS) or not _FIELD_REQUIRED_KEYS <= set(value):
        return False
    if value.get("confirmed") is not True or not isinstance(
        value.get("requires_confirmation"), bool
    ):
        return False
    if not isinstance(value.get("label"), str) or not value["label"].strip():
        return False
    scope = value.get("scope")
    if isinstance(scope, Scope):
        scope_value = scope.value
    elif isinstance(scope, str):
        scope_value = scope
    else:
        return False
    context = value.get("scope_context")
    if scope_value == "global":
        # The shared schema forbids the member itself, even when its JSON value
        # is null; keeping that distinction prevents the HTTP boundary from
        # accepting a shape that other consumers reject.
        if "scope_context" in value:
            return False
    elif scope_value in {"website", "application"}:
        if not is_contract_id(context):
            return False
    else:
        return False
    if "source" in value and not _source_valid(value["source"]):
        return False
    if "options" in value and not _options_valid(value["options"]):
        return False
    if "validation" in value and not _validation_valid(value["validation"]):
        return False
    if "aliases" in value and (
        not isinstance(value["aliases"], list)
        or not all(isinstance(alias, str) and alias.strip() for alias in value["aliases"])
        or len(value["aliases"]) != len(set(value["aliases"]))
    ):
        return False
    try:
        FieldValue.model_validate(dict(value))
    except (TypeError, ValueError):
        return False
    return True


def _record_mapping_valid(value: object) -> bool:
    if (
        not isinstance(value, Mapping)
        or not _nested_members_valid(value, _RECORD_KEYS)
        or not _RECORD_REQUIRED_KEYS <= set(value)
        or not is_contract_id(value.get("record_id"))
    ):
        return False
    if value.get("confirmed") is not True:
        return False
    fields = value.get("fields")
    if not isinstance(fields, list) or not fields:
        return False
    if not all(_field_mapping_valid(item) for item in fields):
        return False
    try:
        RepeatableRecord.model_validate(dict(value))
    except (TypeError, ValueError):
        return False
    return True


def _definition_mapping_valid(value: object) -> bool:
    if (
        not isinstance(value, Mapping)
        or not _nested_members_valid(value, _DEFINITION_KEYS)
        or not _DEFINITION_REQUIRED_KEYS <= set(value)
    ):
        return False
    if value.get("is_custom") is not True or not is_contract_id(value.get("id")):
        return False
    allowed_scopes = value.get("allowed_scopes")
    if (
        not isinstance(allowed_scopes, list)
        or not allowed_scopes
        or not all(
            isinstance(scope, str) and scope in {item.value for item in Scope}
            for scope in allowed_scopes
        )
        or len(allowed_scopes) != len(set(allowed_scopes))
    ):
        return False
    if "aliases" in value and (
        not isinstance(value["aliases"], list)
        or not all(isinstance(alias, str) and alias.strip() for alias in value["aliases"])
        or len(value["aliases"]) != len(set(value["aliases"]))
    ):
        return False
    if "options" in value and not _options_valid(value["options"]):
        return False
    if "validation" in value and not _validation_valid(value["validation"]):
        return False
    try:
        CustomFieldDefinition.model_validate(dict(value))
    except (TypeError, ValueError):
        return False
    return True


def _selection_ids_valid(value: object, key: str) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {key}
        and _string_id_list(value.get(key), allow_empty=False)
    )


def _field_selector_key(value: Mapping[str, Any]) -> tuple[str, Scope, str | None] | None:
    if set(value) - _FIELD_SELECTOR_KEYS:
        return None
    if set(value) not in ({"id", "scope"}, {"id", "scope", "scope_context"}):
        return None
    field_id = value.get("id")
    if not isinstance(field_id, str) or not is_contract_id(field_id):
        return None
    try:
        raw_scope = value.get("scope")
        if not isinstance(raw_scope, (str, Scope)):
            return None
        scope = raw_scope if isinstance(raw_scope, Scope) else Scope(raw_scope)
    except (TypeError, ValueError):
        return None
    context = value.get("scope_context")
    if scope is Scope.GLOBAL:
        if "scope_context" in value:
            return None
        context = None
    elif not is_contract_id(context):
        return None
    return field_id, scope, context


def _selection_field_values_valid(value: object) -> bool:
    if not isinstance(value, Mapping) or set(value) != {"field_values"}:
        return False
    raw_values = value.get("field_values")
    if not isinstance(raw_values, list) or not raw_values:
        return False
    seen: set[tuple[str, Scope, str | None]] = set()
    for raw in raw_values:
        if not isinstance(raw, Mapping):
            return False
        key = _field_selector_key(raw)
        if key is None or key in seen:
            return False
        seen.add(key)
    return True


def _delete_selection_valid(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    if set(value) == {"delete_all"}:
        return value.get("delete_all") is True
    return (
        _selection_ids_valid(value, "field_ids")
        or _selection_field_values_valid(value)
        or _selection_ids_valid(value, "record_ids")
        or _selection_ids_valid(value, "custom_field_definition_ids")
    )


def _export_selection_valid(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    if set(value) == {"all_profile_data"}:
        return value.get("all_profile_data") is True
    if (
        _selection_ids_valid(value, "field_ids")
        or _selection_field_values_valid(value)
        or _selection_ids_valid(value, "record_ids")
    ):
        return True
    if set(value) != {"scopes"}:
        return False
    scopes = value.get("scopes")
    return (
        isinstance(scopes, list)
        and bool(scopes)
        and all(isinstance(item, str) for item in scopes)
        and len(scopes) == len(set(scopes))
        and all(item in {"global", "website", "application"} for item in scopes)
    )


def _body(request: Request, body: object) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    if not isinstance(body, dict):
        return None, _bad_request(request, "request body must be an object")
    request_id, task_id = _identifiers(request, body)
    if body.get("schema_version") != SCHEMA_VERSION:
        return None, _bad_request(
            request, "unsupported schema version", request_id=request_id, task_id=task_id
        )
    if not is_contract_id(body.get("request_id")) or not is_contract_id(body.get("task_id")):
        return None, _bad_request(
            request, "request identifiers are invalid", request_id=request_id, task_id=task_id
        )
    operation = body.get("operation")
    if not isinstance(operation, str) or operation not in {
        "profile.read",
        "profile.upsert",
        "profile.delete",
        "profile.export",
    }:
        return None, _bad_request(
            request, "operation is invalid", request_id=request_id, task_id=task_id
        )
    request.state.request_id = request_id
    request.state.task_id = task_id
    request.state.operation = body.get("operation")
    return body, None


def _router(service: ProfileService) -> APIRouter:
    router = APIRouter()
    replay_cache = _RequestReplayCache()

    @router.post("/v0/profile/read")
    async def profile_read(request: Request, body: object = Body(...)) -> JSONResponse:
        data, error = _body(request, body)
        if error is not None:
            return error
        assert data is not None
        request_id, task_id = _identifiers(request, data)
        if data.get("operation") != "profile.read" or set(data) - _READ_KEYS:
            return _bad_request(
                request, "invalid profile.read request", request_id=request_id, task_id=task_id
            )
        profile_id = data.get("profile_id")
        if not is_contract_id(profile_id):
            return _bad_request(
                request, "profile_id is required", request_id=request_id, task_id=task_id
            )
        snapshot = service.read(profile_id)
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "task_id": task_id,
                "operation": "profile.read.result",
                "task_state": "completed",
                "profile": snapshot.to_dict(),
                "warnings": [],
            }
        )

    @router.post("/v0/profile/upsert")
    @_serialized_mutation(replay_cache)
    async def profile_upsert(request: Request, body: object = Body(...)) -> JSONResponse:
        data, error = _body(request, body)
        if error is not None:
            return error
        assert data is not None
        request_id, task_id = _identifiers(request, data)
        if data.get("operation") != "profile.upsert" or set(data) - _UPSERT_KEYS:
            return _bad_request(
                request, "invalid profile.upsert request", request_id=request_id, task_id=task_id
            )
        profile_id = data.get("profile_id")
        expected = data.get("expected_profile_version")
        fields = data.get("fields", [])
        confirmed = data.get("user_confirmed")
        if (
            not isinstance(profile_id, str)
            or not profile_id.strip()
            or not is_contract_id(profile_id)
            or isinstance(expected, bool)
            or not isinstance(expected, int)
            or expected < 0
            or not isinstance(fields, list)
            or not isinstance(confirmed, bool)
            or data.get("mode", "merge") != "merge"
        ):
            return _bad_request(
                request, "invalid profile.upsert request", request_id=request_id, task_id=task_id
            )
        if not confirmed:
            return _bad_request(
                request,
                "explicit user confirmation is required",
                request_id=request_id,
                task_id=task_id,
                code="CONFIRMATION_REQUIRED",
            )
        records = data.get("records", [])
        definitions = data.get("custom_field_definitions", [])
        delete_field_ids = data.get("delete_field_ids", [])
        delete_record_ids = data.get("delete_record_ids", [])
        delete_definition_ids = data.get("delete_custom_field_definition_ids", [])
        record_order = data.get("record_order")
        if (
            not _mapping_list(fields)
            or not _mapping_list(records)
            or not _mapping_list(definitions)
            or ("records" in data and not records)
            or ("custom_field_definitions" in data and not definitions)
            or not all(_field_mapping_valid(item) for item in fields)
            or not all(_record_mapping_valid(item) for item in records)
            or not all(_definition_mapping_valid(item) for item in definitions)
        ):
            return _bad_request(
                request,
                "invalid profile.upsert mutation members",
                request_id=request_id,
                task_id=task_id,
            )
        if not any(
            isinstance(value, list) and bool(value)
            for value in (
                fields,
                records,
                definitions,
                delete_field_ids,
                delete_record_ids,
                delete_definition_ids,
                record_order,
            )
        ):
            return _bad_request(
                request,
                "profile.upsert requires a non-empty mutation",
                request_id=request_id,
                task_id=task_id,
            )
        if not all(
            _string_id_list(value)
            for value in (delete_field_ids, delete_record_ids, delete_definition_ids)
        ):
            return _bad_request(
                request, "invalid profile.upsert id list", request_id=request_id, task_id=task_id
            )
        if ("delete_record_ids" in data and not delete_record_ids) or (
            "delete_custom_field_definition_ids" in data and not delete_definition_ids
        ):
            return _bad_request(
                request, "invalid profile.upsert id list", request_id=request_id, task_id=task_id
            )
        if record_order is not None and not _string_id_list(record_order, allow_empty=False):
            return _bad_request(
                request, "invalid record_order", request_id=request_id, task_id=task_id
            )
        replay = _replay_response(request, data, replay_cache)
        if replay is not None:
            return replay
        try:
            before = service.read(profile_id)
            snapshot = service.upsert_extended(
                profile_id,
                expected_profile_version=expected,
                fields=fields,
                records=records,
                custom_field_definitions=definitions,
                delete_field_ids=delete_field_ids,
                delete_record_ids=delete_record_ids,
                delete_custom_field_definition_ids=delete_definition_ids,
                record_order=record_order,
                user_confirmed=confirmed,
            )
        except LifecycleError:
            raise
        except (TypeError, ValueError, OverflowError):
            return _bad_request(
                request, "invalid profile.upsert mutation", request_id=request_id, task_id=task_id
            )
        field_ids = [
            str(item.get("id", item.get("field_id", "")))
            for item in fields
            if isinstance(item, Mapping)
        ]
        record_ids = [
            str(item.get("record_id", "")) for item in records if isinstance(item, Mapping)
        ]
        definition_ids = [
            str(item.get("id", "")) for item in definitions if isinstance(item, Mapping)
        ]
        before_field_keys = {
            (field.id, field.scope, field.scope_context) for field in before.fields
        } | {
            (field.id, field.scope, field.scope_context)
            for record in before.records
            for field in record.fields
        }
        after_field_keys = {
            (field.id, field.scope, field.scope_context) for field in snapshot.fields
        } | {
            (field.id, field.scope, field.scope_context)
            for record in snapshot.records
            for field in record.fields
        }
        removed_field_keys = before_field_keys - after_field_keys
        # Report every field identity that disappeared from the committed
        # snapshot, including values removed indirectly when a custom
        # definition is deleted or a record becomes empty.  Keep the order in
        # which the fields appeared before the mutation and de-duplicate IDs
        # because the wire response is ID-based.
        before_field_order = [
            (field.id, field.scope, field.scope_context) for field in before.fields
        ] + [
            (field.id, field.scope, field.scope_context)
            for record in before.records
            for field in record.fields
        ]
        deleted_field_ids = list(
            dict.fromkeys(key[0] for key in before_field_order if key in removed_field_keys)
        )
        before_record_ids = [record.record_id for record in before.records]
        after_record_ids = {record.record_id for record in snapshot.records}
        # Report every record that disappeared during the committed mutation.
        # Field/custom-definition deletion can remove an otherwise empty record,
        # so limiting this list to explicit delete_record_ids would lie about the
        # resulting snapshot.
        deleted_record_ids = [
            record_id for record_id in before_record_ids if record_id not in after_record_ids
        ]
        before_definition_ids = {
            definition.id for definition in before.field_definitions if definition.is_custom
        }
        after_definition_ids = {
            definition.id for definition in snapshot.field_definitions if definition.is_custom
        }
        deleted_definition_ids = [
            definition_id
            for definition_id in dict.fromkeys(delete_definition_ids)
            if definition_id in before_definition_ids and definition_id not in after_definition_ids
        ]
        remaining_order = [
            item.record_id for item in sorted(snapshot.records, key=lambda item: item.position)
        ]
        payload = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "task_id": task_id,
            "operation": "profile.upsert.result",
            "task_state": "completed",
            "profile_id": snapshot.profile_id,
            "profile_version": snapshot.profile_version,
            "written_field_ids": list(dict.fromkeys(field_ids)),
            "written_record_ids": list(dict.fromkeys(record_ids)),
            "written_custom_field_definition_ids": list(dict.fromkeys(definition_ids)),
            "deleted_field_ids": deleted_field_ids,
            "deleted_record_ids": deleted_record_ids,
            "deleted_custom_field_definition_ids": deleted_definition_ids,
            "record_order": remaining_order,
            "warnings": [],
        }
        replay_cache.remember(request_id, data, payload)
        return JSONResponse(payload)

    router.include_router(_lifecycle_router(service, replay_cache))
    return router


def _lifecycle_router(service: ProfileService, replay_cache: _RequestReplayCache) -> APIRouter:
    router = APIRouter()

    @router.post("/v0/profile/delete")
    @_serialized_mutation(replay_cache)
    async def profile_delete(request: Request, body: object = Body(...)) -> JSONResponse:
        data, error = _body(request, body)
        if error is not None:
            return error
        assert data is not None
        request_id, task_id = _identifiers(request, data)
        if data.get("operation") != "profile.delete" or set(data) - _DELETE_KEYS:
            return _bad_request(
                request,
                "invalid profile.delete request",
                request_id=request_id,
                task_id=task_id,
            )
        profile_id = data.get("profile_id")
        expected = data.get("expected_profile_version")
        confirmed = data.get("user_confirmed")
        selection = data.get("selection")
        if (
            not is_contract_id(profile_id)
            or isinstance(expected, bool)
            or not isinstance(expected, int)
            or expected < 0
            or confirmed is not True
            or not isinstance(selection, Mapping)
            or not _delete_selection_valid(selection)
        ):
            code = "CONFIRMATION_REQUIRED" if confirmed is not True else "INVALID_FIELD_VALUE"
            return _bad_request(
                request,
                "invalid profile.delete request"
                if code != "CONFIRMATION_REQUIRED"
                else "explicit user confirmation is required",
                request_id=request_id,
                task_id=task_id,
                code=code,
            )
        replay = _replay_response(request, data, replay_cache)
        if replay is not None:
            return replay
        try:
            result = service.delete(
                profile_id,
                expected_profile_version=expected,
                selection=selection,
                user_confirmed=True,
            )
        except InvalidProfileSelectionError as exc:
            return _bad_request(
                request,
                exc.message,
                request_id=request_id,
                task_id=task_id,
                code=exc.code,
            )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "task_id": task_id,
            "operation": "profile.delete.result",
            **result,
        }
        if result.get("task_state") in {"completed", "partial"}:
            replay_cache.remember(request_id, data, payload)
        return JSONResponse(payload)

    @router.post("/v0/profile/export")
    @_serialized_mutation(replay_cache)
    async def profile_export(request: Request, body: object = Body(...)) -> JSONResponse:
        data, error = _body(request, body)
        if error is not None:
            return error
        assert data is not None
        request_id, task_id = _identifiers(request, data)
        if data.get("operation") != "profile.export" or set(data) - _EXPORT_KEYS:
            return _bad_request(
                request,
                "invalid profile.export request",
                request_id=request_id,
                task_id=task_id,
            )
        profile_id = data.get("profile_id")
        expected = data.get("expected_profile_version")
        confirmed = data.get("user_confirmed")
        selection = data.get("selection")
        destination = data.get("destination")
        if (
            not is_contract_id(profile_id)
            or isinstance(expected, bool)
            or not isinstance(expected, int)
            or expected < 0
        ):
            return _bad_request(
                request,
                "invalid profile.export request",
                request_id=request_id,
                task_id=task_id,
            )
        if confirmed is not True:
            return _bad_request(
                request,
                "explicit user confirmation is required",
                request_id=request_id,
                task_id=task_id,
                code="CONFIRMATION_REQUIRED",
            )
        if (
            data.get("format") != "json"
            or not isinstance(selection, Mapping)
            or not _export_selection_valid(selection)
        ):
            return _bad_request(
                request,
                "invalid profile.export request",
                request_id=request_id,
                task_id=task_id,
                code="INVALID_PROFILE_SELECTION"
                if not isinstance(selection, Mapping)
                else "INVALID_FIELD_VALUE",
            )
        if (
            not isinstance(destination, Mapping)
            or set(destination) - {"kind", "path", "overwrite_existing", "overwrite_confirmed"}
            or destination.get("kind") != "local_file"
            or not isinstance(destination.get("path"), str)
            or not destination.get("path", "").strip()
            or len(destination.get("path", "")) > 4096
            or not isinstance(destination.get("overwrite_existing"), bool)
            or (
                "overwrite_confirmed" in destination
                and destination.get("overwrite_confirmed") is not True
            )
            or (
                destination.get("overwrite_existing") is True
                and destination.get("overwrite_confirmed") is not True
            )
        ):
            return _bad_request(
                request,
                "invalid profile.export destination",
                request_id=request_id,
                task_id=task_id,
                code="EXPORT_FAILED",
            )
        replay = _replay_response(request, data, replay_cache)
        if replay is not None:
            return replay
        try:
            result = service.export(
                profile_id,
                expected_profile_version=expected,
                selection=selection,
                destination=destination["path"],
                user_confirmed=True,
                overwrite_existing=destination["overwrite_existing"],
                overwrite_confirmed=destination.get("overwrite_confirmed", False),
            )
        except (InvalidProfileSelectionError, ExportFailedError) as exc:
            return _bad_request(
                request,
                exc.message,
                request_id=request_id,
                task_id=task_id,
                code=exc.code,
            )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "task_id": task_id,
            "operation": "profile.export.result",
            "task_state": "completed",
            **result,
        }
        replay_cache.remember(request_id, data, payload)
        return JSONResponse(payload)

    return router


def register_profile_routes(app: Any, service: ProfileService) -> None:
    app.include_router(_router(service))


__all__ = ["register_profile_routes"]
