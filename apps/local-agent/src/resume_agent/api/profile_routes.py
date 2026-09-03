"""Profile lifecycle HTTP routes for the F001 local profile library."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from resume_agent.api.app import SCHEMA_VERSION, _error_payload
from resume_agent.profile.service import ProfileService

_READ_KEYS = {"schema_version", "request_id", "task_id", "operation", "profile_id"}
_UPSERT_KEYS = _READ_KEYS | {"expected_profile_version", "user_confirmed", "mode", "fields"}


def _identifiers(request: Request, body: Mapping[str, Any]) -> tuple[str, str]:
    request_id = body.get("request_id") or request.headers.get("x-request-id") or "local-request"
    task_id = body.get("task_id") or request.headers.get("x-task-id") or "local-task"
    return str(request_id), str(task_id)


def _bad_request(request: Request, message: str, *, request_id: str | None = None, task_id: str | None = None) -> JSONResponse:
    payload = _error_payload(
        request,
        code="INVALID_FIELD_VALUE",
        message=message,
        retryable=False,
    )
    if request_id:
        payload["request_id"] = request_id
    if task_id:
        payload["task_id"] = task_id
    return JSONResponse(payload, status_code=400)


def _body(request: Request, body: object) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    if not isinstance(body, dict):
        return None, _bad_request(request, "request body must be an object")
    request_id, task_id = _identifiers(request, body)
    if body.get("schema_version") != SCHEMA_VERSION:
        return None, _bad_request(request, "unsupported schema version", request_id=request_id, task_id=task_id)
    if not isinstance(body.get("request_id", request_id), str) or not isinstance(body.get("task_id", task_id), str):
        return None, _bad_request(request, "request identifiers are invalid", request_id=request_id, task_id=task_id)
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
            return _bad_request(request, "invalid profile.read request", request_id=request_id, task_id=task_id)
        profile_id = data.get("profile_id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            return _bad_request(request, "profile_id is required", request_id=request_id, task_id=task_id)
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
            return _bad_request(request, "invalid profile.upsert request", request_id=request_id, task_id=task_id)
        profile_id = data.get("profile_id")
        expected = data.get("expected_profile_version")
        fields = data.get("fields")
        confirmed = data.get("user_confirmed")
        if (
            not isinstance(profile_id, str)
            or not profile_id.strip()
            or isinstance(expected, bool)
            or not isinstance(expected, int)
            or not isinstance(fields, list)
            or not isinstance(confirmed, bool)
            or data.get("mode", "merge") not in {"merge", "replace"}
        ):
            return _bad_request(request, "invalid profile.upsert request", request_id=request_id, task_id=task_id)
        if not confirmed:
            return _bad_request(request, "explicit user confirmation is required", request_id=request_id, task_id=task_id)
        snapshot = service.upsert(
            profile_id,
            expected_profile_version=expected,
            fields=fields,
            user_confirmed=confirmed,
        )
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "task_id": task_id,
                "operation": "profile.upsert.result",
                "task_state": "completed",
                "profile_id": snapshot.profile_id,
                "profile_version": snapshot.profile_version,
                "written_field_ids": list(dict.fromkeys(str(item.get("id", item.get("field_id", ""))) for item in fields if isinstance(item, Mapping))),
                "deleted_field_ids": [],
                "warnings": [],
            }
        )

    return router


def register_profile_routes(app: Any, service: ProfileService) -> None:
    app.include_router(_router(service))


__all__ = ["register_profile_routes"]
