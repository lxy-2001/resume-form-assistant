"""Document parsing orchestration behind narrow parser seams."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .docx_parser import parse_docx
from .errors import OcrUnavailableError, UnsupportedDocumentError
from .input import DOCX_MEDIA_TYPE, PDF_MEDIA_TYPE, validate_document_input
from .models import ParsedSegment
from .ocr import OcrEngine, run_ocr
from .pdf_parser import parse_pdf

MAX_PDF_PAGES = 50


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    document_id: str
    filename: str
    media_type: str
    size_bytes: int
    sha256: str
    segments: tuple[ParsedSegment, ...]
    ocr_used: bool = False


def parse_document(
    path: str | Path,
    *,
    pdf_parser: Callable[[Path], list[ParsedSegment]] = parse_pdf,
    docx_parser: Callable[[Path], list[ParsedSegment]] = parse_docx,
    ocr_engine: OcrEngine | None = None,
    document_id: str | None = None,
    ocr_mode: str = "auto",
) -> ParsedDocument:
    document = validate_document_input(path)
    if document.media_type == DOCX_MEDIA_TYPE:
        segments = docx_parser(document.path)
        return ParsedDocument(
            document_id=document_id or document.sha256[:24],
            filename=document.filename,
            media_type=document.media_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            segments=tuple(segments),
        )
    if document.media_type != PDF_MEDIA_TYPE:
        raise UnsupportedDocumentError("document type is not supported")
    page_count = len(PdfReader(document.path).pages)
    if page_count > MAX_PDF_PAGES:
        raise UnsupportedDocumentError("document exceeds the configured page limit")
    segments = pdf_parser(document.path)
    if segments and ocr_mode != "force":
        return ParsedDocument(
            document_id=document_id or document.sha256[:24],
            filename=document.filename,
            media_type=document.media_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            segments=tuple(segments),
        )
    if ocr_mode == "never":
        return ParsedDocument(
            document_id=document_id or document.sha256[:24],
            filename=document.filename,
            media_type=document.media_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            segments=tuple(segments),
            ocr_used=False,
        )
    if ocr_engine is None:
        raise OcrUnavailableError("local OCR engine is unavailable")
    ocr_segments: list[ParsedSegment] = []
    for page_number in range(1, page_count + 1):
        ocr_segments.extend(run_ocr(document.path, engine=ocr_engine, page_number=page_number))
    return ParsedDocument(
        document_id=document_id or document.sha256[:24],
        filename=document.filename,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        sha256=document.sha256,
        segments=tuple(ocr_segments),
        ocr_used=True,
    )
