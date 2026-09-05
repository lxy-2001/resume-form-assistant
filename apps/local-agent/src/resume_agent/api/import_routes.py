"""Local document import preview and confirmation routes."""

from __future__ import annotations

import base64
import binascii
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from docx.opc.exceptions import PackageNotFoundError
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse
from pypdf.errors import PdfReadError

from resume_agent.api.app import SCHEMA_VERSION, _error_payload
from resume_agent.imports.service import ImportService
from resume_agent.parsing.errors import ParsingError, UnsupportedDocumentError
from resume_agent.parsing.pipeline import parse_document
from resume_agent.parsing.tesseract_ocr import TesseractOcrEngine

_PREVIEW_KEYS = {
    "schema_version",
    "request_id",
    "task_id",
    "operation",
    "source",
    "consent",
    "ocr_mode",
    "content_base64",
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
_PDF = "application/pdf"
_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024


def _identifiers(request: Request, body: dict[str, Any]) -> tuple[str, str]:
    return str(
        body.get("request_id") or request.headers.get("x-request-id") or "local-request"
    ), str(body.get("task_id") or request.headers.get("x-task-id") or "local-task")


def _bad(
    request: Request, *, request_id: str, task_id: str, code: str, message: str, status: int = 400
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


def _router(import_service: ImportService) -> APIRouter:
    router = APIRouter()

    @router.post("/v0/profile/import/preview")
    async def preview(request: Request, body: object = Body(...)) -> JSONResponse:
        request.state.operation = "profile.import.preview"
        if not isinstance(body, dict) or set(body) - _PREVIEW_KEYS:
            return _bad(
                request,
                request_id="local-request",
                task_id="local-task",
                code="INVALID_FIELD_VALUE",
                message="import preview request is invalid",
            )
        request_id, task_id = _identifiers(request, body)
        source = body.get("source")
        encoded = body.get("content_base64")
        consent = body.get("consent")
        if (
            body.get("schema_version") != SCHEMA_VERSION
            or body.get("operation") != "profile.import.preview"
            or not isinstance(source, dict)
            or not isinstance(encoded, str)
            or source.get("media_type") not in {_PDF, _DOCX}
            or not isinstance(source.get("document_id"), str)
            or not isinstance(source.get("filename"), str)
            or not isinstance(consent, dict)
            or consent.get("remote_model_allowed") is not False
        ):
            return _bad(
                request,
                request_id=request_id,
                task_id=task_id,
                code="INVALID_FIELD_VALUE",
                message="document content is required",
            )
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            return _bad(
                request,
                request_id=request_id,
                task_id=task_id,
                code="INVALID_FIELD_VALUE",
                message="document content is invalid",
            )
        if len(content) > _MAX_DOCUMENT_BYTES:
            return _bad(
                request,
                request_id=request_id,
                task_id=task_id,
                code="UNSUPPORTED_DOCUMENT",
                message="document exceeds the configured size limit",
            )
        media_type = source.get("media_type")
        suffix = (
            ".pdf"
            if media_type == "application/pdf"
            else ".docx"
            if media_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else ".bin"
        )
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="resume-import-", suffix=suffix, delete=False
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                temporary_path = Path(temporary.name)
            try:
                document = parse_document(
                    temporary_path,
                    document_id=str(source["document_id"]),
                    ocr_mode=str(body.get("ocr_mode", "auto")),
                    ocr_engine=TesseractOcrEngine(),
                )
                if (
                    source.get("size_bytes") is not None
                    and source["size_bytes"] != document.size_bytes
                ):
                    raise UnsupportedDocumentError("document size does not match metadata")
                if source.get("sha256") and source["sha256"].lower() != document.sha256.lower():
                    raise UnsupportedDocumentError("document hash does not match metadata")
                task = import_service.preview(document, task_id=task_id)
            except ParsingError as exc:
                return _bad(
                    request,
                    request_id=request_id,
                    task_id=task_id,
                    code=exc.code,
                    message=exc.message,
                )
            except (OSError, ValueError, zipfile.BadZipFile, PackageNotFoundError, PdfReadError):
                return _bad(
                    request,
                    request_id=request_id,
                    task_id=task_id,
                    code="DOCUMENT_PARSE_FAILED",
                    message="document could not be parsed",
                )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "task_id": task_id,
                "operation": "profile.import.preview.result",
                "task_state": "awaiting_user_review",
                "document_id": task.document.document_id,
                "candidates": list(task.candidates),
                "warnings": (
                    [
                        {
                            "code": "NO_TEXT_EXTRACTED",
                            "message": "document text could not be extracted locally",
                            "severity": "warning",
                        }
                    ]
                    if not task.document.segments
                    else []
                ),
                "ocr_used": task.document.ocr_used,
                "model_used": False,
                "remote_data_sent": False,
                "consent_recorded": False,
            }
        )

    @router.post("/v0/profile/import/confirm")
    async def confirm(request: Request, body: object = Body(...)) -> JSONResponse:
        request.state.operation = "profile.import.confirm"
        if not isinstance(body, dict) or set(body) - _CONFIRM_KEYS:
            return _bad(
                request,
                request_id="local-request",
                task_id="local-task",
                code="INVALID_FIELD_VALUE",
                message="import confirmation request is invalid",
            )
        request_id, task_id = _identifiers(request, body)
        decisions = body.get("decisions")
        if (
            body.get("schema_version") != SCHEMA_VERSION
            or body.get("operation") != "profile.import.confirm"
            or not isinstance(body.get("profile_id"), str)
            or not isinstance(body.get("expected_profile_version"), int)
            or body.get("expected_profile_version", -1) < 0
            or not isinstance(decisions, list)
            or not decisions
        ):
            return _bad(
                request,
                request_id=request_id,
                task_id=task_id,
                code="INVALID_FIELD_VALUE",
                message="import confirmation request is invalid",
            )
        try:
            result = import_service.confirm(
                task_id,
                decisions=decisions,
                profile_id=str(body["profile_id"]),
                expected_profile_version=int(body["expected_profile_version"]),
            )
        except ParsingError as exc:
            return _bad(
                request,
                request_id=request_id,
                task_id=task_id,
                code=exc.code,
                message=exc.message,
                status=409,
            )
        except (KeyError, TypeError, ValueError):
            return _bad(
                request,
                request_id=request_id,
                task_id=task_id,
                code="INVALID_FIELD_VALUE",
                message="import confirmation request is invalid",
            )
        return JSONResponse(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": request_id,
                "task_id": task_id,
                "operation": "profile.import.confirm.result",
                "task_state": "completed",
                **result,
            }
        )

    return router


def register_import_routes(app: Any, import_service: ImportService) -> None:
    app.include_router(_router(import_service))
