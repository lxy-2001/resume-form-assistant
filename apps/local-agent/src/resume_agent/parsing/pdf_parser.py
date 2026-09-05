"""Text-layer PDF extraction."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from .models import ParsedSegment


def parse_pdf(path: str | Path) -> list[ParsedSegment]:
    reader = PdfReader(path)
    segments: list[ParsedSegment] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            segments.append(ParsedSegment(text=text, location=f"page {page_number}"))
    return segments
