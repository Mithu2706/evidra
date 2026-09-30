"""OCR engines behind a common interface.

`auto` prefers RapidOCR (pure pip install, runs locally via ONNX Runtime),
then the Tesseract CLI, and otherwise reports OCR as unavailable — in which
case the visual comparison is explicitly marked "Not assessed".
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

from .base import OCREngine


class OCRUnavailable(Exception):
    pass


class RapidOCREngine(OCREngine):
    name = "rapidocr"
    _lock = threading.Lock()
    _engine = None

    def available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except Exception:
            return False
        return True

    def recognize(self, image_path: Path) -> str:
        with self._lock:
            if RapidOCREngine._engine is None:
                from rapidocr_onnxruntime import RapidOCR

                RapidOCREngine._engine = RapidOCR()
            result, _ = RapidOCREngine._engine(str(image_path))
        if not result:
            return ""
        # Sort roughly top-to-bottom, left-to-right.
        items = sorted(result, key=lambda r: (round(r[0][0][1] / 20), r[0][0][0]))
        return "\n".join(item[1] for item in items if item[1].strip())


class TesseractEngine(OCREngine):
    name = "tesseract"

    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    def recognize(self, image_path: Path) -> str:
        proc = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "3"],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[:300] or "tesseract failed")
        return proc.stdout


class NullOCREngine(OCREngine):
    name = "none"

    def available(self) -> bool:
        return False

    def recognize(self, image_path: Path) -> str:  # pragma: no cover - never called
        raise OCRUnavailable("No OCR engine configured")


def build_ocr_engine(preference: str) -> OCREngine:
    candidates: list[OCREngine]
    if preference == "rapidocr":
        candidates = [RapidOCREngine()]
    elif preference == "tesseract":
        candidates = [TesseractEngine()]
    elif preference == "none":
        candidates = []
    else:
        candidates = [RapidOCREngine(), TesseractEngine()]
    for engine in candidates:
        if engine.available():
            return engine
    return NullOCREngine()
