"""Evidence Pack schema — the contract between ingestion and AI analysis.

The AI layer only ever receives an EvidencePack, never the raw file. Every
unit has a stable id (e.g. ``slide_06``) that AI findings must cite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["slide", "document", "github", "video", "website"]
LocationKind = Literal["slide_number", "page_number", "file_path", "timestamp", "url"]

IntegrityStatus = Literal[
    "no_discrepancy_detected",
    "potential_discrepancy",
    "suspicious_instruction_detected",
    "manual_review_required",
]

INTEGRITY_SEVERITY_ORDER: dict[str, int] = {
    "no_discrepancy_detected": 0,
    "potential_discrepancy": 1,
    "manual_review_required": 2,
    "suspicious_instruction_detected": 3,
}


class SourceLocation(BaseModel):
    kind: LocationKind
    value: str | int


class IntegrityFlag(BaseModel):
    """A single integrity observation. Deliberately descriptive, not accusatory."""

    slide_id: str | None = None
    type: Literal[
        "not_visible_in_render",  # text layer content not found in the rendered slide
        "low_contrast_text",  # text colour ~ background colour
        "invisible_text_layer",  # PDF text render mode "invisible" / zero opacity
        "tiny_text",  # font size below legibility threshold
        "off_slide_content",  # shape positioned outside the visible slide
        "hidden_slide",  # PPTX slide marked hidden
        "instruction_like_text",  # hidden/unrendered text resembling an instruction to evaluators
        "speaker_note_instruction",  # speaker notes resembling an instruction to evaluators
        "visible_evaluator_address",  # visible text addressing evaluators; informational only
        "visual_check_unavailable",  # OCR/rendering unavailable, comparison not performed
    ]
    status: IntegrityStatus
    location: Literal["slide_text", "speaker_notes", "slide"] = "slide_text"
    excerpt: str = ""
    detail: str = ""
    withheld_from_ai: bool = False


class NotAssessedItem(BaseModel):
    area: str
    reason: str
    slide_id: str | None = None


class EvidenceUnit(BaseModel):
    """One slide/page (or, in future, one file / video segment / web page)."""

    slide_id: str = Field(..., description="Stable id, e.g. slide_06")
    page_number: int
    source_type: SourceType = "slide"
    source_location: SourceLocation
    title: str | None = None
    text: str = ""
    speaker_notes: str | None = None
    image_path: str | None = None
    ocr_text: str | None = None
    ocr_status: Literal["completed", "empty", "failed", "unavailable", "not_run"] = "not_run"
    has_visual_content: bool = False
    links: list[str] = Field(default_factory=list)
    integrity_flags: list[IntegrityFlag] = Field(default_factory=list)
    processing_notes: list[str] = Field(default_factory=list)


class IntegrityReport(BaseModel):
    status: IntegrityStatus
    summary: str
    flags: list[IntegrityFlag] = Field(default_factory=list)
    method: str = ""
    limitations: str = (
        "This check compares the document's text layer with the rendered slides and scans "
        "speaker notes. It cannot detect every form of manipulation."
    )


class EvidencePack(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    submission_id: int
    source_file: str
    file_type: Literal["pdf", "pptx"]
    page_count: int
    units: list[EvidenceUnit]
    not_assessed: list[NotAssessedItem] = Field(default_factory=list)
    integrity: IntegrityReport
    processing_status: Literal["complete", "partial"] = "complete"
    ingestion: dict[str, str] = Field(default_factory=dict)  # component -> implementation
    created_at: datetime

    def unit(self, slide_id: str) -> EvidenceUnit | None:
        return next((u for u in self.units if u.slide_id == slide_id), None)
