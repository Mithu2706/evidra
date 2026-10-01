"""Ingestion interfaces.

Each step of the ingestion pipeline is an interface so implementations can be
swapped (e.g. a cloud document parser, a different OCR engine, a
vision-model integrity check) without touching the rest of the system.

    Submission → FileValidator → DocumentParser → PageRenderer → OCREngine
               → IntegrityAnalyzer → EvidencePack
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class IngestionError(Exception):
    """Raised when a document cannot be processed at all."""


@dataclass
class TextSpanSignal:
    """Structural evidence that a piece of text may not be visible to a human."""

    text: str
    reason: str  # low_contrast_text | invisible_text_layer | tiny_text | off_slide_content
    detail: str = ""


@dataclass
class ParsedUnit:
    page_number: int
    title: str | None = None
    text: str = ""
    speaker_notes: str | None = None
    links: list[str] = field(default_factory=list)
    has_visual_content: bool = False
    has_embedded_media: bool = False
    hidden: bool = False  # PPTX "hidden slide"
    structural_signals: list[TextSpanSignal] = field(default_factory=list)
    processing_notes: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    file_type: str
    units: list[ParsedUnit]
    # A PDF that can be rasterised page-by-page. For PDF inputs this is the file
    # itself; for PPTX it is produced by a converter (may be None if unavailable).
    renderable_pdf: Path | None
    # Maps unit index -> page index inside `renderable_pdf` (hidden slides are
    # usually skipped by converters, so this is not always the identity).
    render_page_map: dict[int, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderedPage:
    image_path: Path | None
    thumb_path: Path | None
    error: str | None = None


class FileValidator(ABC):
    @abstractmethod
    def validate(self, path: Path, *, original_filename: str) -> str:
        """Return the detected file type or raise ValidationFailed."""


class DocumentParser(ABC):
    file_types: tuple[str, ...] = ()
    name: str = "parser"

    @abstractmethod
    def parse(self, path: Path, work_dir: Path) -> ParsedDocument: ...


class PageRenderer(ABC):
    name: str = "renderer"

    @abstractmethod
    def render(self, doc: ParsedDocument, out_dir: Path) -> list[RenderedPage]: ...


class OCREngine(ABC):
    name: str = "ocr"

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def recognize(self, image_path: Path) -> str: ...
