"""Shared input for all AI stages, built from the Evidence Pack.

Content that the integrity check flagged as hidden (and marked
`withheld_from_ai`) is removed here, so no stage — heuristic or LLM — ever
sees it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from rapidfuzz import fuzz

from ..ingestion.textutil import normalize, split_sentences
from ..schemas.evidence import EvidencePack, EvidenceUnit

WITHHELD_MARK = "[content withheld by integrity check]"


@dataclass
class CriterionSpec:
    id: int
    name: str
    description: str
    weight: float


@dataclass
class UnitView:
    """What the analysis is allowed to see for one slide."""

    unit: EvidenceUnit
    text: str
    notes: str
    image_text: str  # OCR text not already present in the text layer
    withheld: bool = False

    @property
    def slide_id(self) -> str:
        return self.unit.slide_id

    @property
    def title(self) -> str:
        return self.unit.title or ""

    @cached_property
    def sentences(self) -> list[str]:
        title = normalize(self.title)
        out = []
        for s in split_sentences(self.text):
            if normalize(s) == title:
                continue
            out.append(s)
        return out

    @cached_property
    def note_sentences(self) -> list[str]:
        return split_sentences(self.notes)

    @cached_property
    def image_sentences(self) -> list[str]:
        return split_sentences(self.image_text)

    @property
    def all_text(self) -> str:
        return "\n".join(p for p in (self.title, self.text, self.notes, self.image_text) if p)


@dataclass
class AnalysisContext:
    pack: EvidencePack
    criteria: list[CriterionSpec]
    scale_max: int
    team_name: str
    submission_title: str
    round_name: str = ""
    views: list[UnitView] = field(init=False)

    def __post_init__(self) -> None:
        self.views = [build_view(u) for u in self.pack.units]

    def view(self, slide_id: str) -> UnitView | None:
        return next((v for v in self.views if v.slide_id == slide_id), None)

    @property
    def visible_views(self) -> list[UnitView]:
        return [v for v in self.views if not v.withheld]

    @property
    def total_weight(self) -> float:
        return sum(c.weight for c in self.criteria) or 1.0


def _withheld_excerpts(unit: EvidenceUnit, location: str) -> list[str]:
    return [
        normalize(f.excerpt.rstrip("…"))
        for f in unit.integrity_flags
        if f.withheld_from_ai and f.location == location and f.excerpt
    ]


def _drop_withheld_lines(text: str, excerpts: list[str]) -> str:
    if not excerpts or not text:
        return text
    kept = []
    for line in text.splitlines():
        norm = normalize(line)
        if norm and any(fuzz.partial_ratio(norm, ex) >= 90 for ex in excerpts if len(ex) >= 8):
            if not kept or kept[-1] != WITHHELD_MARK:
                kept.append(WITHHELD_MARK)
            continue
        kept.append(line)
    return "\n".join(kept)


def build_view(unit: EvidenceUnit) -> UnitView:
    if any(f.withheld_from_ai and f.location == "slide" for f in unit.integrity_flags):
        return UnitView(unit=unit, text=WITHHELD_MARK, notes="", image_text="", withheld=True)

    text = _drop_withheld_lines(unit.text, _withheld_excerpts(unit, "slide_text"))
    notes = _drop_withheld_lines(unit.speaker_notes or "", _withheld_excerpts(unit, "speaker_notes"))

    image_lines: list[str] = []
    if unit.ocr_text and unit.has_visual_content:
        text_norm = normalize(unit.text)
        for line in unit.ocr_text.splitlines():
            norm = normalize(line)
            if len(norm) < 4:
                continue
            if text_norm and fuzz.partial_ratio(norm, text_norm) >= 80:
                continue
            image_lines.append(line.strip())
    return UnitView(unit=unit, text=text, notes=notes, image_text="\n".join(image_lines))
