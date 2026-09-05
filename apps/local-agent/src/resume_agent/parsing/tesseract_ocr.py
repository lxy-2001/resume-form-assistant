"""Optional local Tesseract OCR adapter."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pypdfium2 as pdfium  # type: ignore[import-untyped]

from .errors import OcrUnavailableError, ParsingError
from .models import ParsedSegment


class TesseractOcrEngine:
    """Run a locally installed Tesseract binary without network access."""

    def __init__(self, command: str = "tesseract") -> None:
        self.command = command

    @property
    def available(self) -> bool:
        return shutil.which(self.command) is not None or Path(self.command).is_file()

    def recognize(self, image: object, *, page_number: int) -> list[ParsedSegment]:
        if not self.available:
            raise OcrUnavailableError("local OCR engine is unavailable")
        source = Path(str(image))
        with tempfile.TemporaryDirectory(prefix="resume-ocr-") as directory:
            image_path = self._render(source, page_number, Path(directory))
            try:
                result = subprocess.run(
                    [self.command, str(image_path), "stdout", "--psm", "6"],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
            except subprocess.TimeoutExpired as exc:
                raise ParsingError("local OCR timed out") from exc
            if result.returncode != 0:
                raise ParsingError("local OCR failed")
            text = result.stdout.strip()
            if not text:
                return []
            return [
                ParsedSegment(text=text, location=f"page {page_number}", extraction_method="ocr")
            ]

    @staticmethod
    def _render(source: Path, page_number: int, directory: Path) -> Path:
        if source.suffix.lower() not in {".pdf"}:
            return source
        try:
            pdf = pdfium.PdfDocument(str(source))
            page = pdf.get_page(page_number - 1)
            bitmap = page.render(scale=2)
            image_path = directory / f"page-{page_number}.png"
            bitmap.to_pil().save(image_path)
            page.close()
            pdf.close()
            return image_path
        except Exception as exc:
            raise ParsingError("document page could not be rendered for OCR") from exc
