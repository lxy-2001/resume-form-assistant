from pathlib import Path

import pytest

from resume_agent.parsing.errors import UnsupportedDocumentError
from resume_agent.parsing.input import DocumentInput, validate_document_input


def test_accepts_pdf_and_records_metadata(tmp_path: Path) -> None:
    path = tmp_path / "resume.pdf"
    path.write_bytes(b"synthetic pdf")

    document = validate_document_input(path)

    assert isinstance(document, DocumentInput)
    assert document.filename == "resume.pdf"
    assert document.media_type == "application/pdf"
    assert document.size_bytes == len(b"synthetic pdf")
    assert len(document.sha256) == 64


def test_rejects_doc_before_reading_contents(tmp_path: Path) -> None:
    path = tmp_path / "resume.doc"
    path.write_bytes(b"legacy word")

    with pytest.raises(UnsupportedDocumentError):
        validate_document_input(path)


def test_rejects_path_outside_configured_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"pdf")

    with pytest.raises(UnsupportedDocumentError):
        validate_document_input(outside, allowed_root=allowed)


def test_rejects_oversized_document_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "large.pdf"
    path.write_bytes(b"0123456789")

    with pytest.raises(UnsupportedDocumentError, match="size"):
        validate_document_input(path, max_bytes=5)
