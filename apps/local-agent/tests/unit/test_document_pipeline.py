from pathlib import Path

import pytest
from pypdf import PdfWriter

from resume_agent.parsing.errors import UnsupportedDocumentError
from resume_agent.parsing.models import ParsedSegment
from resume_agent.parsing.pipeline import parse_document


class FakeOcr:
    available = True

    def recognize(self, image: object, *, page_number: int) -> list[ParsedSegment]:
        return [
            ParsedSegment("姓名：OCR 用户", f"page {page_number} region 1", extraction_method="ocr")
        ]


def test_pdf_without_text_uses_local_ocr(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with path.open("wb") as stream:
        writer.write(stream)

    result = parse_document(path, pdf_parser=lambda _: [], ocr_engine=FakeOcr())

    assert result.ocr_used is True
    assert result.segments[0].extraction_method == "ocr"


def test_pipeline_rejects_pdf_over_page_limit(tmp_path: Path) -> None:
    path = tmp_path / "many-pages.pdf"
    writer = PdfWriter()
    for _ in range(51):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as stream:
        writer.write(stream)

    with pytest.raises(UnsupportedDocumentError, match="page limit"):
        parse_document(path, ocr_mode="never")
