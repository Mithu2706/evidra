"""Grounds AI evidence references against the Evidence Pack.

* References to slide ids that do not exist are dropped.
* Excerpts are fuzzy-matched against what the analysis was allowed to see
  (text, speaker notes, OCR image text) and marked `verified` accordingly.
* Findings that must be evidence-backed but end up with no valid reference
  are removed rather than shown without a source.
"""

from __future__ import annotations

import logging

from rapidfuzz import fuzz

from ..ingestion.textutil import normalize, truncate
from ..schemas.ai import EvidenceRef
from .context import AnalysisContext

log = logging.getLogger(__name__)

EXCERPT_MATCH_THRESHOLD = 85


def ground_refs(refs: list[EvidenceRef], ctx: AnalysisContext) -> list[EvidenceRef]:
    grounded: list[EvidenceRef] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        view = ctx.view(ref.slide_id.strip().lower())
        if view is None:
            log.info("Dropping evidence ref to unknown slide %r", ref.slide_id)
            continue
        excerpt = truncate(ref.excerpt, 240)
        norm = normalize(excerpt)
        via, verified = "unknown", False
        if norm and not view.withheld:
            for source, content in (
                ("text", view.text),
                ("speaker_notes", view.notes),
                ("ocr", view.image_text),
            ):
                if content and fuzz.partial_ratio(norm, normalize(content)) >= EXCERPT_MATCH_THRESHOLD:
                    via, verified = source, True
                    break
        key = (view.slide_id, norm)
        if key in seen:
            continue
        seen.add(key)
        grounded.append(
            EvidenceRef(
                slide_id=view.slide_id,
                excerpt=excerpt,
                page_number=view.unit.page_number,
                verified=verified,
                via=via,  # type: ignore[arg-type]
            )
        )
    return grounded
