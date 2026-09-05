"""User-selected document validation and metadata."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .errors import UnsupportedDocumentError

PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SUPPORTED_MEDIA_TYPES = {PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE}


@dataclass(frozen=True, slots=True)
class DocumentInput:
    path: Path
    filename: str
    media_type: str
    size_bytes: int
    sha256: str


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PDF_MEDIA_TYPE
    if suffix == ".docx":
        return DOCX_MEDIA_TYPE
    raise UnsupportedDocumentError("document type is not supported")


def validate_document_input(
    path: str | Path,
    *,
    allowed_root: Path | None = None,
    max_bytes: int = 16 * 1024 * 1024,
) -> DocumentInput:
    candidate = Path(path)
    if allowed_root is not None:
        try:
            candidate.resolve(strict=True).relative_to(Path(allowed_root).resolve(strict=True))
        except (FileNotFoundError, ValueError) as exc:
            raise UnsupportedDocumentError("document path is outside the allowed root") from exc
    if not candidate.is_file():
        raise UnsupportedDocumentError("document file is not readable")
    media_type = _media_type(candidate)
    size_bytes = candidate.stat().st_size
    if size_bytes > max_bytes:
        raise UnsupportedDocumentError("document exceeds the configured size limit")
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return DocumentInput(
        path=candidate,
        filename=candidate.name,
        media_type=media_type,
        size_bytes=size_bytes,
        sha256=digest.hexdigest(),
    )
