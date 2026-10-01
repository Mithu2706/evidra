"""File validation: type sniffing (not just extensions), size and page limits."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from .base import FileValidator


class ValidationFailed(Exception):
    pass


@dataclass
class SubmissionLimits:
    max_file_size_mb: int = 25
    max_pages: int = 30
    allowed_file_types: tuple[str, ...] = ("pdf", "pptx")


def sniff_file_type(path: Path) -> str | None:
    with path.open("rb") as fh:
        head = fh.read(8)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile:
            return None
        if "[Content_Types].xml" in names and any(n.startswith("ppt/") for n in names):
            return "pptx"
    return None


class DefaultFileValidator(FileValidator):
    def __init__(self, limits: SubmissionLimits):
        self.limits = limits

    def validate(self, path: Path, *, original_filename: str) -> str:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.limits.max_file_size_mb:
            raise ValidationFailed(
                f"File is {size_mb:.1f} MB; this round accepts files up to "
                f"{self.limits.max_file_size_mb} MB."
            )
        if path.stat().st_size == 0:
            raise ValidationFailed("File is empty.")
        detected = sniff_file_type(path)
        if detected is None:
            raise ValidationFailed(
                "Unsupported or unreadable file. Upload a PDF or PowerPoint (.pptx) file."
            )
        if detected not in self.limits.allowed_file_types:
            raise ValidationFailed(f"This round does not accept .{detected} files.")
        ext = Path(original_filename).suffix.lower().lstrip(".")
        if ext and ext != detected:
            raise ValidationFailed(
                f"File extension .{ext} does not match its contents ({detected.upper()})."
            )
        return detected
