"""Ingestion pipeline: turns an uploaded file into an Evidence Pack."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from ..schemas.evidence import (
    EvidencePack,
    EvidenceUnit,
    IntegrityFlag,
    NotAssessedItem,
    SourceLocation,
)
from .base import DocumentParser, IngestionError, OCREngine, PageRenderer, RenderedPage
from .integrity import IntegrityAnalyzer, UnitIntegrityInput
from .ocr import build_ocr_engine
from .pdf_parser import PDFParser
from .pptx_parser import PPTXParser
from .rendering import PyMuPDFRenderer
from .validation import DefaultFileValidator, SubmissionLimits

log = logging.getLogger(__name__)

VISUAL_SLIDE_WORD_THRESHOLD = 25


@dataclass
class IngestionResult:
    pack: EvidencePack
    rendered: list[RenderedPage]
    renderable_pdf: Path | None


def slide_key(page_number: int) -> str:
    return f"slide_{page_number:02d}"


class IngestionPipeline:
    def __init__(
        self,
        *,
        parsers: list[DocumentParser] | None = None,
        renderer: PageRenderer | None = None,
        ocr: OCREngine | None = None,
        integrity: IntegrityAnalyzer | None = None,
        ocr_preference: str = "auto",
        render_width_px: int = 1600,
    ):
        self.parsers = parsers or [PDFParser(), PPTXParser()]
        self.renderer = renderer or PyMuPDFRenderer(render_width_px)
        self.ocr = ocr or build_ocr_engine(ocr_preference)
        self.integrity = integrity or IntegrityAnalyzer()

    def parser_for(self, file_type: str) -> DocumentParser:
        for parser in self.parsers:
            if file_type in parser.file_types:
                return parser
        raise IngestionError(f"No parser registered for .{file_type}")

    def run(
        self,
        path: Path,
        *,
        original_filename: str,
        submission_id: int,
        limits: SubmissionLimits,
        work_dir: Path,
        on_stage=lambda stage: None,
    ) -> IngestionResult:
        on_stage("validating")
        file_type = DefaultFileValidator(limits).validate(path, original_filename=original_filename)

        on_stage("parsing")
        parsed = self.parser_for(file_type).parse(path, work_dir)
        if len(parsed.units) > limits.max_pages:
            raise IngestionError(
                f"Submission has {len(parsed.units)} pages; this round allows at most {limits.max_pages}."
            )

        on_stage("rendering")
        rendered = self.renderer.render(parsed, work_dir / "pages")

        on_stage("ocr")
        ocr_available = self.ocr.available()
        ocr_results: list[tuple[str | None, str]] = []
        for page in rendered:
            if page.image_path is None:
                ocr_results.append((None, "not_run"))
            elif not ocr_available:
                ocr_results.append((None, "unavailable"))
            else:
                try:
                    text = self.ocr.recognize(page.image_path).strip()
                    ocr_results.append((text, "completed" if text else "empty"))
                except Exception as exc:
                    log.warning("OCR failed on %s: %s", page.image_path, exc)
                    ocr_results.append((None, "failed"))

        on_stage("integrity")
        units: list[EvidenceUnit] = []
        not_assessed: list[NotAssessedItem] = []
        all_flags: list[IntegrityFlag] = []
        location_kind = "slide_number" if file_type == "pptx" else "page_number"
        # PDF pitch decks are still "slides" to judges, so both formats use the same label.
        label_word = "Slide"

        for idx, (unit, page) in enumerate(zip(parsed.units, rendered)):
            sid = slide_key(unit.page_number)
            ocr_text, ocr_status = ocr_results[idx]
            flags = self.integrity.analyze_unit(
                UnitIntegrityInput(
                    slide_id=sid,
                    page_number=unit.page_number,
                    unit=unit,
                    ocr_text=ocr_text,
                    ocr_status=ocr_status,
                    rendered=page.image_path is not None,
                )
            )
            all_flags.extend(flags)
            notes = list(unit.processing_notes)
            if page.error and not unit.hidden:
                notes.append(page.error)
            units.append(
                EvidenceUnit(
                    slide_id=sid,
                    page_number=unit.page_number,
                    source_type="slide",
                    source_location=SourceLocation(kind=location_kind, value=unit.page_number),
                    title=unit.title,
                    text=unit.text,
                    speaker_notes=unit.speaker_notes,
                    image_path=str(page.image_path) if page.image_path else None,
                    ocr_text=ocr_text,
                    ocr_status=ocr_status,  # type: ignore[arg-type]
                    has_visual_content=unit.has_visual_content,
                    links=unit.links,
                    integrity_flags=flags,
                    processing_notes=notes,
                )
            )
            not_assessed.extend(
                self._not_assessed_for(unit, page, ocr_status, sid, label_word, parsed.renderable_pdf is not None)
            )

        if parsed.renderable_pdf is None:
            not_assessed.insert(
                0,
                NotAssessedItem(
                    area="Slide rendering",
                    reason="The document could not be rendered to images"
                    + (f" ({'; '.join(parsed.notes)})" if parsed.notes else "")
                    + ". Visual content and the visual integrity comparison were not assessed.",
                ),
            )
        elif not ocr_available:
            not_assessed.append(
                NotAssessedItem(
                    area="Visual integrity comparison",
                    reason="No OCR engine is available, so extracted text could not be compared with the "
                    "rendered slides. Integrity check limited to structural checks.",
                )
            )

        page_labels = {u.slide_id: f"{label_word} {u.page_number}" for u in units}
        report = self.integrity.summarize(all_flags, ocr_available=ocr_available, page_labels=page_labels)
        partial = parsed.renderable_pdf is None or any(
            "failed" in note.lower() for u in units for note in u.processing_notes
        )

        pack = EvidencePack(
            submission_id=submission_id,
            source_file=original_filename,
            file_type=file_type,  # type: ignore[arg-type]
            page_count=len(units),
            units=units,
            not_assessed=not_assessed,
            integrity=report,
            processing_status="partial" if partial else "complete",
            ingestion={
                "validator": "magic-bytes+limits",
                "parser": self.parser_for(file_type).name,
                "renderer": self.renderer.name if parsed.renderable_pdf else "unavailable",
                "ocr": self.ocr.name if ocr_available else "unavailable",
                "integrity": self.integrity.name,
            },
            created_at=datetime.now(timezone.utc),
        )
        return IngestionResult(pack=pack, rendered=rendered, renderable_pdf=parsed.renderable_pdf)

    @staticmethod
    def _not_assessed_for(
        unit, page: RenderedPage, ocr_status: str, sid: str, label_word: str, renderable: bool
    ) -> list[NotAssessedItem]:
        label = f"{label_word} {unit.page_number}"
        items: list[NotAssessedItem] = []
        if unit.hidden:
            items.append(
                NotAssessedItem(
                    area=f"{label} (hidden slide)",
                    reason=f"{label} is marked hidden in the presentation; its content was excluded from AI analysis.",
                    slide_id=sid,
                )
            )
            return items
        if page.image_path is None and renderable:
            items.append(
                NotAssessedItem(
                    area=f"{label} visual content",
                    reason=f"{label} could not be rendered, so its visual content was not inspected.",
                    slide_id=sid,
                )
            )
        words = len((unit.text or "").split())
        if unit.has_visual_content and words < VISUAL_SLIDE_WORD_THRESHOLD:
            if ocr_status == "completed":
                reason = (
                    f"{label} is mostly visual (images/diagrams). Text inside images was read with OCR, "
                    "but diagrams and charts were not interpreted."
                )
            else:
                reason = f"{label} is mostly visual (images/diagrams) and its visual content could not be interpreted."
            items.append(NotAssessedItem(area=f"{label} images/diagrams", reason=reason, slide_id=sid))
        for link in unit.links:
            host = urlparse(link).netloc or link
            kind = "video" if any(v in host for v in ("youtube", "youtu.be", "vimeo", "loom")) else "external"
            items.append(
                NotAssessedItem(
                    area=f"{label} linked {kind} content",
                    reason=f"External content linked on {label} ({host}) could not be accessed. "
                    "External links, demos and videos are not analyzed in this version.",
                    slide_id=sid,
                )
            )
        if unit.has_embedded_media:
            items.append(
                NotAssessedItem(
                    area=f"{label} embedded media",
                    reason=f"Embedded media on {label} (video/audio/object) was not analyzed.",
                    slide_id=sid,
                )
            )
        for note in unit.processing_notes:
            if "failed" in note.lower():
                items.append(NotAssessedItem(area=f"{label} text", reason=note, slide_id=sid))
        return items
