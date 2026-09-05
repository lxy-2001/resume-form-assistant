from pathlib import Path

import pytest

from resume_agent.parsing.errors import OcrUnavailableError
from resume_agent.parsing.ocr import run_ocr


class MissingEngine:
    available = False

    def recognize(self, image: object, *, page_number: int) -> list[object]:
        raise AssertionError("unavailable engine must not be called")


def test_missing_local_ocr_engine_is_reported_without_fake_text(tmp_path: Path) -> None:
    image = tmp_path / "page.png"
    image.write_bytes(b"not a real image")

    with pytest.raises(OcrUnavailableError):
        run_ocr(image, engine=MissingEngine())
