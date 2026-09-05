"""Local document parsing primitives for F002."""

from .errors import OcrUnavailableError, UnsupportedDocumentError
from .input import DocumentInput, validate_document_input
from .models import ParsedSegment

__all__ = [
    "DocumentInput",
    "OcrUnavailableError",
    "ParsedSegment",
    "UnsupportedDocumentError",
    "validate_document_input",
]
