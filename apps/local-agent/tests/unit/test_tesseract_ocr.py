from pathlib import Path

from resume_agent.parsing.tesseract_ocr import TesseractOcrEngine


def test_tesseract_backend_reports_unavailable_command() -> None:
    engine = TesseractOcrEngine(command="definitely-not-installed-tesseract")

    assert engine.available is False


def test_tesseract_backend_can_be_constructed_with_explicit_command(tmp_path: Path) -> None:
    engine = TesseractOcrEngine(command=str(tmp_path / "tesseract.exe"))

    assert engine.command.endswith("tesseract.exe")
