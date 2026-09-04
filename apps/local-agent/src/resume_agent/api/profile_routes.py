"""Profile lifecycle HTTP routes for the F001 local profile library."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from resume_agent.api.app import SCHEMA_VERSION, _error_payload
from resume_agent.profile.errors import (
    ExportFailedError,
    InvalidProfileSelectionError,
    LifecycleError,
)
from resume_agent.profile.models import is_contract_id
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


def _field_mapping_valid(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    field_id = value.get("id", value.get("field_id"))
    if not is_contract_id(field_id):
        return False
    scope = value.get("scope", "global")
    context = value.get("scope_context")
    if scope == "global":
        return context is None
    if scope in {"website", "application"}:
        return is_contract_id(context)
    return False


def _record_mapping_valid(value: object) -> bool:
    if not isinstance(value, Mapping) or not is_contract_id(value.get("record_id")):
        return False
    fields = value.get("fields")
    return isinstance(fields, list) and all(_field_mapping_valid(item) for item in fields)


def _definition_mapping_valid(value: object) -> bool:
    return isinstance(value, Mapping) and is_contract_id(value.get("id"))


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
    if not isinstance(operation, str) or not operation.strip():
        return None, _bad_request(
            request, "operation is invalid", request_id=request_id, task_id=task_id
        )
    request.state.request_id = request_id
    request.state.task_id = task_id
    request.state.operation = body.get("operation")
    return body, None


def _router(service: ProfileService) -> APIRouter:
    router = APIRouter()

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
        if not isinstance(profile_id, str) or not profile_id.strip():
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
        if not all(
            _string_id_list(value)
            for value in (delete_field_ids, delete_record_ids, delete_definition_ids)
        ):
            return _bad_request(
                request, "invalid profile.upsert id list", request_id=request_id, task_id=task_id
            )
        if record_order is not None and not _string_id_list(record_order, allow_empty=False):
            return _bad_request(
                request, "invalid record_order", request_id=request_id, task_id=task_id
            )
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
        except (TypeError, ValueError):
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
        deleted_field_ids = [
            field_id
            for field_id in dict.fromkeys(delete_field_ids)
            if any(field.id == field_id for field in before.fields)
        ]
        remaining_order = [
            item.record_id for item in sorted(snapshot.records, key=lambda item: item.position)
        ]
        return JSONResponse(
            {
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
                "deleted_record_ids": list(dict.fromkeys(str(item) for item in delete_record_ids)),
                "deleted_custom_field_definition_ids": list(
                    dict.fromkeys(str(item) for item in delete_definition_ids)
                ),
                "record_order": remaining_order,
                "warnings": [],
            }
        )

    router.include_router(_lifecycle_router(service))
    return router


def _lifecycle_router(service: ProfileService) -> APIRouter:
    router = APIRouter()

    @router.post("/v0/profile/delete")
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
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "task_id": task_id,
                "operation": "profile.delete.result",
                **result,
            }
        )

    @router.post("/v0/profile/export")
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
        if data.get("format") != "json" or not isinstance(selection, Mapping):
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
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "task_id": task_id,
                "operation": "profile.export.result",
                **result,
            }
        )

    return router


def register_profile_routes(app: Any, service: ProfileService) -> None:
    app.include_router(_router(service))


__all__ = ["register_profile_routes"]
