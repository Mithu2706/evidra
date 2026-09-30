"""Basic V1 submission-integrity check.

Method
------
1. Compare each line of the extracted text layer with the OCR text of the
   rendered slide (fuzzy matching). Lines that cannot be found are candidates
   for content a human would not see.
2. Add structural signals from the parser (invisible render mode, text colour
   ≈ background, tiny fonts, off-slide boxes, hidden slides).
3. Only escalate when candidate hidden text *resembles an instruction to the
   evaluator* (e.g. "ignore previous instructions", "rate this project highly").
4. Scan speaker notes separately — they are legitimately invisible, so only
   instruction-like text is flagged.

Visible persuasive text is not treated as an injection. Mismatches are
reported with cautious language, never as proof of manipulation, and the
check never claims a submission is "clean".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from ..schemas.evidence import INTEGRITY_SEVERITY_ORDER, IntegrityFlag, IntegrityReport
from .base import ParsedUnit, TextSpanSignal
from .textutil import normalize, truncate

MATCH_THRESHOLD = 62  # partial_ratio below this => "not found in render"
MIN_LINE_CHARS = 14
MIN_LINE_WORDS = 3

INSTRUCTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|earlier|all|other)\b.{0,20}\b(instruction|prompt|rule|guideline|direction)s?\b",
        r"\b(give|assign|award|grant)\b.{0,25}\b(this|the|our)\b.{0,15}\b(submission|project|team|proposal|entry)\b.{0,25}\b(high|highest|top|perfect|maximum|max|full|10|100)\b",
        r"\brate\b.{0,25}\b(this|the|our)\b.{0,15}\b(submission|project|team|proposal|entry)\b.{0,20}\b(high(ly)?|10|100|top|excellent|as the best)\b",
        r"\b(always|must)\b.{0,15}\b(select|choose|pick|rank|advance|shortlist)\b.{0,20}\b(this|the|our)\b.{0,10}\b(team|project|submission)\b",
        r"\bsystem\s*(instruction|prompt|message|override)s?\b",
        r"\b(judge|evaluator|grader|reviewer|assistant|model|llm|ai)\s*(instruction|directive|note)s?\s*:",
        r"\b(note|message|instruction)s?\s+to\s+(the\s+)?(ai|llm|model|assistant|judge|evaluator|grader)\b",
        r"\b(if you are|as an?|you are an?)\s+(ai|language model|llm|automated (judge|evaluator|grader))\b",
        r"\b(score|mark)\b.{0,20}\b(10\s*/\s*10|100\s*/\s*100|full marks|maximum (score|points))\b",
        r"\bdo not (mention|report|flag)\b.{0,30}\b(this|these|weakness|issue|instruction)",
    ]
]


def looks_like_instruction(text: str) -> bool:
    flat = " ".join((text or "").split())
    return any(p.search(flat) for p in INSTRUCTION_PATTERNS)


@dataclass
class UnitIntegrityInput:
    slide_id: str
    page_number: int
    unit: ParsedUnit
    ocr_text: str | None
    ocr_status: str  # completed | empty | failed | unavailable | not_run
    rendered: bool


_STRUCTURAL_LABEL = {
    "low_contrast_text": "text colour nearly matches the background",
    "invisible_text_layer": "text is present in the file but set to be invisible",
    "tiny_text": "text is set in an unreadably small font",
    "off_slide_content": "text is positioned outside the visible slide area",
}


class IntegrityAnalyzer:
    name = "text-vs-render-fuzzy-v1"

    def analyze_unit(self, item: UnitIntegrityInput) -> list[IntegrityFlag]:
        unit, sid = item.unit, item.slide_id
        flags: list[IntegrityFlag] = []
        structural_texts: set[str] = set()

        # Hidden slide: its entire content is invisible in presentation mode.
        if unit.hidden and unit.text:
            instr = looks_like_instruction(unit.text)
            flags.append(
                IntegrityFlag(
                    slide_id=sid,
                    type="instruction_like_text" if instr else "hidden_slide",
                    status="suspicious_instruction_detected" if instr else "potential_discrepancy",
                    location="slide",
                    excerpt=truncate(unit.text, 220),
                    detail="Slide is marked hidden and would not be shown during a presentation."
                    + (" Its text resembles an instruction to evaluators." if instr else ""),
                    withheld_from_ai=True,
                )
            )
            structural_texts.add(normalize(unit.text))

        # Structural visibility signals from the parser.
        for sig in unit.structural_signals:
            flags.append(self._structural_flag(sid, sig))
            structural_texts.add(normalize(sig.text))

        # Text-layer vs rendered-slide comparison.
        if not unit.hidden and unit.text:
            if item.ocr_status in ("completed", "empty") and item.rendered:
                flags.extend(self._compare(sid, unit.text, item.ocr_text or "", structural_texts))
            elif item.ocr_status == "failed" or not item.rendered:
                flags.append(
                    IntegrityFlag(
                        slide_id=sid,
                        type="visual_check_unavailable",
                        status="manual_review_required",
                        location="slide",
                        detail=(
                            "The slide could not be rendered"
                            if not item.rendered
                            else "The rendered slide could not be read"
                        )
                        + ", so its text layer could not be compared with what is visible. "
                        "Please review this slide manually.",
                    )
                )

        # Speaker notes: only instruction-like content matters.
        if unit.speaker_notes:
            for line in _lines(unit.speaker_notes):
                if looks_like_instruction(line):
                    flags.append(
                        IntegrityFlag(
                            slide_id=sid,
                            type="speaker_note_instruction",
                            status="suspicious_instruction_detected",
                            location="speaker_notes",
                            excerpt=truncate(line, 220),
                            detail="Speaker notes contain text resembling an instruction to evaluators. "
                            "Notes are not visible on the slide.",
                            withheld_from_ai=True,
                        )
                    )
        return flags

    def _structural_flag(self, sid: str, sig: TextSpanSignal) -> IntegrityFlag:
        instr = looks_like_instruction(sig.text)
        label = _STRUCTURAL_LABEL.get(sig.reason, sig.reason)
        return IntegrityFlag(
            slide_id=sid,
            type="instruction_like_text" if instr else sig.reason,  # type: ignore[arg-type]
            status="suspicious_instruction_detected" if instr else "potential_discrepancy",
            location="slide_text",
            excerpt=truncate(sig.text, 220),
            detail=f"Possible hidden content: {label}."
            + (" The text resembles an instruction to evaluators." if instr else "")
            + (f" ({sig.detail})" if sig.detail and sig.detail not in label else ""),
            withheld_from_ai=True,
        )

    def _compare(self, sid: str, text: str, ocr_text: str, already: set[str]) -> list[IntegrityFlag]:
        ocr_norm = normalize(ocr_text)
        flags: list[IntegrityFlag] = []
        unmatched: list[str] = []
        visible_instructions: list[str] = []
        comparable = 0
        for line in _lines(text):
            norm = normalize(line)
            if len(norm) < MIN_LINE_CHARS or len(norm.split()) < MIN_LINE_WORDS:
                continue
            if any(norm in s or s in norm for s in already if s):
                continue
            comparable += 1
            score = fuzz.partial_ratio(norm, ocr_norm) if ocr_norm else 0
            if score < MATCH_THRESHOLD:
                unmatched.append(line)
            elif looks_like_instruction(line):
                visible_instructions.append(line)

        instr_lines = [ln for ln in unmatched if looks_like_instruction(ln)]
        benign = [ln for ln in unmatched if ln not in instr_lines]
        if instr_lines:
            flags.append(
                IntegrityFlag(
                    slide_id=sid,
                    type="instruction_like_text",
                    status="suspicious_instruction_detected",
                    location="slide_text",
                    excerpt=truncate(" ".join(instr_lines), 220),
                    detail="Text in the file's text layer was not found on the rendered slide and resembles an "
                    "instruction to evaluators.",
                    withheld_from_ai=True,
                )
            )
        # Tolerate isolated OCR misses; report only a meaningful share of missing text.
        if benign and (len(benign) >= 2 and len(benign) / max(comparable, 1) >= 0.25):
            flags.append(
                IntegrityFlag(
                    slide_id=sid,
                    type="not_visible_in_render",
                    status="potential_discrepancy",
                    location="slide_text",
                    excerpt=truncate(" / ".join(benign), 220),
                    detail=f"{len(benign)} line(s) of extracted text could not be matched to the rendered slide. "
                    "This can be caused by OCR limitations and is not necessarily hidden content.",
                )
            )
        for line in visible_instructions:
            flags.append(
                IntegrityFlag(
                    slide_id=sid,
                    type="visible_evaluator_address",
                    status="no_discrepancy_detected",
                    location="slide_text",
                    excerpt=truncate(line, 220),
                    detail="Visible text addresses evaluators directly. It is visible to human judges, so it is "
                    "not treated as hidden content; shown for awareness only.",
                )
            )
        return flags

    def summarize(
        self, flags: list[IntegrityFlag], *, ocr_available: bool, page_labels: dict[str, str]
    ) -> IntegrityReport:
        status = "no_discrepancy_detected"
        for f in flags:
            if INTEGRITY_SEVERITY_ORDER[f.status] > INTEGRITY_SEVERITY_ORDER[status]:
                status = f.status
        if not ocr_available and INTEGRITY_SEVERITY_ORDER[status] < INTEGRITY_SEVERITY_ORDER["manual_review_required"]:
            status = "manual_review_required"

        def where(st: str) -> str:
            labels = sorted(
                {page_labels.get(f.slide_id or "", "") for f in flags if f.status == st and f.slide_id},
                key=lambda s: int(s.split()[-1]) if s.split()[-1].isdigit() else 0,
            )
            labels = [label for label in labels if label]
            if len(labels) > 4:
                return f"{len(labels)} slides"
            return ", ".join(labels) or "this submission"

        if status == "no_discrepancy_detected":
            summary = "No hidden-content discrepancy detected."
        elif status == "potential_discrepancy":
            summary = f"Potential hidden/inconsistent content detected on {where(status)}."
        elif status == "suspicious_instruction_detected":
            summary = (
                f"Potential hidden instruction-like text detected on {where(status)}. "
                "The flagged text was withheld from AI analysis. Please review the original slide."
            )
        elif not ocr_available:
            summary = (
                "Integrity check incomplete: visual comparison unavailable (no OCR engine). "
                "Manual review required."
            )
        else:
            summary = f"Integrity check could not be completed for {where(status)}. Manual review required."

        return IntegrityReport(
            status=status,  # type: ignore[arg-type]
            summary=summary,
            flags=flags,
            method="Fuzzy comparison of the text layer against OCR of rendered slides, structural visibility "
            "checks, and a speaker-note scan for instruction-like text.",
        )


def _lines(text: str) -> list[str]:
    return [ln.strip(" •-–—*\t") for ln in (text or "").splitlines() if ln.strip(" •-–—*\t")]
