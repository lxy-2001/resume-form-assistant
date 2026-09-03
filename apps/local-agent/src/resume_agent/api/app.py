"""Safety-focused FastAPI application shell for the local agent.

This module deliberately contains no profile routes or persistence.  It provides
only the boundary that later routes mount: loopback/origin checks, a request
size limit, a health endpoint, and contract-shaped redacted errors.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from resume_agent.config import AppConfig
from resume_agent.privacy.redaction import redact_details, redact_text
from resume_agent.profile.errors import LifecycleError
from resume_agent.storage.errors import StorageError

SCHEMA_VERSION = "0.1"
_DEFAULT_DATA_DIR_NAME = ".resume-agent"
_SAFE_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _id_from_header(request: Request, name: str, fallback: str) -> str:
    value = request.headers.get(name, "").strip()
    if value and len(value) <= 128 and all(char.isalnum() or char in "._:-" for char in value):
        return value
    return fallback


def _error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    retryable: bool,
    details: dict[str, Any] | None = None,
    failed_operation: str | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": redact_text(message),
        "retryable": retryable,
    }
    if details:
        error["details"] = redact_details(details)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "request_id": _id_from_header(request, "x-request-id", "local-request"),
        "task_id": _id_from_header(request, "x-task-id", "local-task"),
        "operation": "error",
        "error": error,
    }
    if failed_operation in {"profile.read", "profile.upsert", "profile.delete", "profile.export"}:
        payload["failed_operation"] = failed_operation
    return payload


def _typed_error_response(request: Request, exc: LifecycleError, status_code: int) -> JSONResponse:
    failed_operation = request.headers.get("x-operation")
    payload = _error_payload(
        request,
        code=exc.code,
        message=exc.message,
        retryable=isinstance(exc, StorageError),
        details=exc.details,
        failed_operation=failed_operation,
    )
    return JSONResponse(payload, status_code=status_code)


class _RequestSafetyMiddleware(BaseHTTPMiddleware):
    """Apply local-origin and bounded-body checks before route execution."""

    def __init__(
        self,
        app: Any,
        *,
        max_body_bytes: int,
        allowed_origins: frozenset[str],
        require_loopback: bool,
    ) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes
        self.allowed_origins = allowed_origins
        self.require_loopback = require_loopback

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Any:
        if self.require_loopback:
            client = request.client
            if client is not None and client.host not in _SAFE_CLIENTS:
                return JSONResponse(
                    _error_payload(
                        request,
                        code="LOOPBACK_REQUIRED",
                        message="loopback access required",
                        retryable=False,
                    ),
                    status_code=403,
                )

        origin = request.headers.get("origin")
        if origin and origin not in self.allowed_origins:
            return JSONResponse(
                _error_payload(
                    request,
                    code="ORIGIN_NOT_ALLOWED",
                    message="origin is not allowed",
                    retryable=False,
                ),
                status_code=403,
            )

        length = request.headers.get("content-length")
        if length is not None:
            try:
                declared_length = int(length)
            except ValueError:
                return JSONResponse(
                    _error_payload(
                        request,
                        code="INVALID_CONTENT_LENGTH",
                        message="invalid content length",
                        retryable=False,
                    ),
                    status_code=400,
                )
            if declared_length < 0 or declared_length > self.max_body_bytes:
                return JSONResponse(
                    _error_payload(
                        request,
                        code="REQUEST_TOO_LARGE",
                        message="request body too large",
                        retryable=False,
                    ),
                    status_code=413,
                )

        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            body = await request.body()
            if len(body) > self.max_body_bytes:
                return JSONResponse(
                    _error_payload(
                        request,
                        code="REQUEST_TOO_LARGE",
                        message="request body too large",
                        retryable=False,
                    ),
                    status_code=413,
                )
            request._body = body
        return await call_next(request)


def _default_config() -> AppConfig:
    # Constructing this path does not create or inspect it; callers can inject a
    # platform-specific root explicitly for tests and packaged deployments.
    return AppConfig(Path.home() / _DEFAULT_DATA_DIR_NAME)


def create_app(
    config: AppConfig | None = None,
    *,
    allowed_origins: Iterable[str] | None = None,
    require_loopback: bool = True,
) -> FastAPI:
    """Build the local API app without starting a server or performing I/O."""

    effective_config = config or _default_config()
    configured_origins = (
        frozenset(allowed_origins)
        if allowed_origins is not None
        else frozenset(getattr(effective_config, "allowed_origins", ()))
    )
    app = FastAPI(title=effective_config.app_name)
    app.add_middleware(
        _RequestSafetyMiddleware,
        max_body_bytes=effective_config.request_limit,
        allowed_origins=configured_origins,
        require_loopback=require_loopback,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "schema_version": SCHEMA_VERSION}

    @app.exception_handler(StorageError)
    async def storage_error(request: Request, exc: StorageError) -> JSONResponse:
        status = 503 if exc.code == "STORAGE_UNAVAILABLE" else 500
        return _typed_error_response(request, exc, status)

    @app.exception_handler(LifecycleError)
    async def lifecycle_error(request: Request, exc: LifecycleError) -> JSONResponse:
        return _typed_error_response(request, exc, 409)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _: Exception) -> JSONResponse:
        return JSONResponse(
            _error_payload(
                request,
                code="INTERNAL_ERROR",
                message="internal server error",
                retryable=False,
            ),
            status_code=500,
        )

    return app


__all__ = ["create_app"]
