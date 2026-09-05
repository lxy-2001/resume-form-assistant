"""Privacy-safe F002 parsing errors."""

from __future__ import annotations

from typing import ClassVar

from resume_agent.profile.errors import LifecycleError


class ParsingError(LifecycleError):
    code: ClassVar[str] = "DOCUMENT_PARSE_FAILED"


class UnsupportedDocumentError(ParsingError):
    code = "UNSUPPORTED_DOCUMENT"


class OcrUnavailableError(ParsingError):
    code = "OCR_UNAVAILABLE"
