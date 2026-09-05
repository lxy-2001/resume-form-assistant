from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from resume_agent.api.app import SCHEMA_VERSION, _error_payload
from resume_agent.api.profile_routes import (
    _replay_response,
    _RequestReplayCache,
    _serialized_mutation,
)
from resume_agent.normalization.service import NormalizationService
from resume_agent.profile.errors import ProfileError
from resume_agent.profile.models import is_contract_id

_PREVIEW_KEYS = {
    "schema_version",
    "request_id",
    "task_id",
    "operation",
    "source_task_id",
    "profile_id",
}
_CONFIRM_KEYS = {
    "schema_version",
    "request_id",
    "task_id",
    "operation",
    "profile_id",
    "expected_profile_version",
    "decisions",
}
_CANCEL_KEYS = {"schema_version", "request_id", "task_id", "operation"}
_DECISION_KEYS = {"candidate_id", "decision", "value", "target_scope", "user_confirmed"}


def _bad(
    request: Request,
    message: str,
    *,
    request_id: str,
    task_id: str,
    code: str = "INVALID_FIELD_VALUE",
    status: int = 400,
) -> JSONResponse:
    payload = _error_payload(
        request,
        code=code,
        message=message,
        retryable=False,
        failed_operation=request.state.operation,
    )
    payload["request_id"] = request_id
    payload["task_id"] = task_id
    return JSONResponse(payload, status_code=status)


def _error_code(message: str) -> str:
    if "expired" in message:
        return "TASK_EXPIRED"
    if "version" in message or "stale" in message:
        return "STALE_PROFILE_VERSION"
    if "storage" in message:
        return "STORAGE_FAILURE"
    return "INVALID_FIELD_VALUE"


def _profile_error_response(
    request: Request, exc: ProfileError, *, request_id: str, task_id: str
) -> JSONResponse:
    status = 409 if exc.code in {"STALE_PROFILE_VERSION", "PROFILE_NOT_FOUND"} else 500
    return _bad(
        request, exc.message, request_id=request_id, task_id=task_id, code=exc.code, status=status
    )


def register_normalization_routes(
    app: Any, service: NormalizationService, *, replay_cache: _RequestReplayCache
) -> None:
    router = APIRouter()

    @router.post("/v0/profile/normalize/preview")
    async def preview(request: Request, body: object = Body(...)) -> JSONResponse:
        request.state.operation = "profile.normalize.preview"
        data = body if isinstance(body, dict) else {}
        request_id = str(data.get("request_id") or "local-request")
        task_id = str(data.get("task_id") or "local-task")
        if (
            set(data) - _PREVIEW_KEYS
            or data.get("schema_version") != SCHEMA_VERSION
            or data.get("operation") != "profile.normalize.preview"
            or not is_contract_id(request_id)
            or not is_contract_id(task_id)
            or not is_contract_id(data.get("source_task_id"))
            or not is_contract_id(data.get("profile_id"))
        ):
            return _bad(
                request,
                "normalization preview request is invalid",
                request_id=request_id,
                task_id=task_id,
            )
        try:
            task = service.preview(
                str(data["source_task_id"]), profile_id=str(data["profile_id"]), task_id=task_id
            )
        except ProfileError as exc:
            return _profile_error_response(request, exc, request_id=request_id, task_id=task_id)
        except ValueError as exc:
            return _bad(
                request,
                str(exc),
                request_id=request_id,
                task_id=task_id,
                code=_error_code(str(exc)),
                status=409,
            )
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "task_id": task_id,
                "operation": "profile.normalize.preview.result",
                **task.to_dict(),
            }
        )

    @router.post("/v0/profile/normalize/confirm")
    @_serialized_mutation(replay_cache)
    async def confirm(request: Request, body: object = Body(...)) -> JSONResponse:
        request.state.operation = "profile.normalize.confirm"
        data = body if isinstance(body, dict) else {}
        request_id = str(data.get("request_id") or "local-request")
        task_id = str(data.get("task_id") or "local-task")
        replay = _replay_response(request, data, replay_cache) if isinstance(body, dict) else None
        if replay is not None:
            return replay
        if (
            set(data) - _CONFIRM_KEYS
            or data.get("schema_version") != SCHEMA_VERSION
            or data.get("operation") != "profile.normalize.confirm"
            or not is_contract_id(request_id)
            or not is_contract_id(task_id)
            or not is_contract_id(data.get("profile_id"))
            or not isinstance(data.get("expected_profile_version"), int)
            or not isinstance(data.get("decisions"), list)
            or not data["decisions"]
            or any(
                not isinstance(item, Mapping)
                or set(item) - _DECISION_KEYS
                or not isinstance(item.get("candidate_id"), str)
                or item.get("decision") not in {"accept", "modify", "skip", "reject"}
                or item.get("user_confirmed") is not True
                for item in data["decisions"]
            )
        ):
            return _bad(
                request,
                "normalization confirmation request is invalid",
                request_id=request_id,
                task_id=task_id,
            )
        try:
            result = service.confirm(
                task_id,
                decisions=data["decisions"],
                profile_id=str(data["profile_id"]),
                expected_profile_version=int(data["expected_profile_version"]),
            )
        except ProfileError as exc:
            return _profile_error_response(request, exc, request_id=request_id, task_id=task_id)
        except (TypeError, ValueError) as exc:
            return _bad(
                request,
                str(exc),
                request_id=request_id,
                task_id=task_id,
                code=_error_code(str(exc)),
                status=409,
            )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "task_id": task_id,
            "operation": "profile.normalize.confirm.result",
            "task_state": "completed",
            **result,
        }
        replay_cache.remember(request_id, data, payload)
        return JSONResponse(payload)

    @router.post("/v0/profile/normalize/cancel")
    @_serialized_mutation(replay_cache)
    async def cancel(request: Request, body: object = Body(...)) -> JSONResponse:
        request.state.operation = "profile.normalize.cancel"
        data = body if isinstance(body, dict) else {}
        request_id = str(data.get("request_id") or "local-request")
        task_id = str(data.get("task_id") or "local-task")
        if (
            set(data) - _CANCEL_KEYS
            or data.get("schema_version") != SCHEMA_VERSION
            or data.get("operation") != "profile.normalize.cancel"
            or not is_contract_id(request_id)
            or not is_contract_id(task_id)
        ):
            return _bad(
                request,
                "normalization cancellation request is invalid",
                request_id=request_id,
                task_id=task_id,
            )
        try:
            cancelled = service.cancel(task_id)
        except ValueError as exc:
            return _bad(
                request,
                str(exc),
                request_id=request_id,
                task_id=task_id,
                code=_error_code(str(exc)),
                status=409,
            )
        if not cancelled:
            return _bad(
                request,
                "normalization task is unavailable",
                request_id=request_id,
                task_id=task_id,
                code="TASK_UNAVAILABLE",
                status=409,
            )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "task_id": task_id,
            "operation": "profile.normalize.cancel.result",
            "task_state": "completed",
            "cancelled": True,
        }
        replay_cache.remember(request_id, data, payload)
        return JSONResponse(payload)

    app.include_router(router)
