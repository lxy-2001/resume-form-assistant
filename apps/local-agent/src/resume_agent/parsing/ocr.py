"""Local OCR backend seam with fail-closed availability handling."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .errors import OcrUnavailableError
from .models import ParsedSegment


class OcrEngine(Protocol):
    @property
    def available(self) -> bool: ...

    def recognize(self, image: object, *, page_number: int) -> list[ParsedSegment]: ...


def run_ocr(
    image_path: str | Path,
    *,
    engine: OcrEngine,
    page_number: int = 1,
) -> list[ParsedSegment]:
    if not engine.available:
        raise OcrUnavailableError("local OCR engine is unavailable")
    # The concrete image decoder and engine remain behind this seam.  F002 never
    # fabricates OCR text when the backend is unavailable.
    return engine.recognize(Path(image_path), page_number=page_number)
