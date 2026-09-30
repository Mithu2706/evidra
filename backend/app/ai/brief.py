"""Deterministic assembly of the Judge Brief and the (hidden) AI assessment.

Sections that must never be invented by a model — the evidence map, the
integrity summary, "Not assessed" and rubric coverage — are built here from
the Evidence Pack and the validated stage outputs.
"""

from __future__ import annotations

from ..ingestion.textutil import truncate
from ..schemas.ai import (
    AIAssessment,
    BriefProvenance,
    BriefWriterOutput,
    EvidenceHighlight,
    EvidenceRef,
    ExtractionOutput,
    IntegritySummary,
    JudgeBrief,
    RubricAnalysisOutput,
    RubricCoverage,
    VerificationOutput,
    VerifyItem,
)
from .context import AnalysisContext
from .stages.heuristic.signals import HIGHLIGHT_ORDER

INTEGRITY_MESSAGES = {
    "no_discrepancy_detected": "✓ No hidden-content discrepancy detected.",
    "potential_discrepancy": "⚠ {summary}",
    "suspicious_instruction_detected": "⚠ {summary}",
    "manual_review_required": "⚠ {summary}",
}


def integrity_verify_items(ctx: AnalysisContext) -> list[VerifyItem]:
    """Integrity findings become Verify-These items regardless of AI engine."""
    items: list[VerifyItem] = []
    for flag in ctx.pack.integrity.flags:
        if flag.status not in ("suspicious_instruction_detected", "potential_discrepancy"):
            continue
        unit = ctx.pack.unit(flag.slide_id) if flag.slide_id else None
        where = f"Slide {unit.page_number}" if unit else "the submission"
        suspicious = flag.status == "suspicious_instruction_detected"
        items.append(
            VerifyItem(
                id=f"i{len(items) + 1}",
                title=(
                    f"Potential hidden instruction-like text on {where}"
                    if suspicious
                    else f"Potential hidden/inconsistent content on {where}"
                ),
                description=flag.detail
                + (" This text was withheld from AI analysis." if flag.withheld_from_ai else "")
                + " Open the original slide to check what a presenter would show.",
                type="integrity",
                severity="high" if suspicious else "medium",
                # The excerpt is quoted for the judge, but it is not grounded as
                # "evidence" because the analysis never saw it.
                evidence=[
                    EvidenceRef(
                        slide_id=flag.slide_id,
                        excerpt=truncate(flag.excerpt, 200),
                        page_number=unit.page_number,
                        verified=True,
                        via="text" if flag.location != "speaker_notes" else "speaker_notes",
                    )
                ]
                if unit and flag.excerpt
                else [],
            )
        )
    return items


def assemble_brief(
    ctx: AnalysisContext,
    extraction: ExtractionOutput,
    rubric: RubricAnalysisOutput,
    verification: VerificationOutput,
    writer: BriefWriterOutput,
    provenance: BriefProvenance,
) -> JudgeBrief:
    by_topic = {t.topic: t for t in extraction.topics}
    ordered = [k for k in HIGHLIGHT_ORDER if k in by_topic] + [
        t.topic for t in extraction.topics if t.topic not in HIGHLIGHT_ORDER and t.topic != "team"
    ]
    highlights = [
        EvidenceHighlight(id=f"e{i + 1}", label=by_topic[k].label, evidence=by_topic[k].evidence[:3])
        for i, k in enumerate(ordered)
        if by_topic[k].evidence
    ]

    items_by_id = {i.id: i for i in verification.items}
    ordered_items = [items_by_id[i] for i in writer.verify_order if i in items_by_id]
    ordered_items += [i for i in verification.items if i not in ordered_items]
    verify = integrity_verify_items(ctx) + ordered_items[:7]

    coverage: list[RubricCoverage] = []
    for c in rubric.criteria:
        n = len({r.slide_id for r in c.evidence})
        coverage.append(
            RubricCoverage(
                criterion_id=c.criterion_id,
                criterion=c.criterion,
                evidence=c.evidence[:4],
                coverage="not_found" if n == 0 else ("limited" if n == 1 else "addressed"),
            )
        )

    report = ctx.pack.integrity
    return JudgeBrief(
        overview=writer.overview,
        target_users=extraction.target_users,
        evidence_highlights=highlights,
        strengths=writer.strengths,
        verify_these=verify,
        not_assessed=ctx.pack.not_assessed,
        integrity=IntegritySummary(
            status=report.status,
            message=INTEGRITY_MESSAGES[report.status].format(summary=report.summary),
            flags=list(report.flags),
            limitations=report.limitations,
        ),
        rubric_coverage=coverage,
        provenance=provenance,
    )


def assemble_assessment(
    ctx: AnalysisContext, rubric: RubricAnalysisOutput, *, engine: str, model: str | None
) -> AIAssessment:
    weights = {c.id: c.weight for c in ctx.criteria}
    assessed_weight = 0.0
    weighted = 0.0
    for c in rubric.criteria:
        if c.assessed and c.score is not None and c.criterion_id in weights:
            c.score = max(1.0, min(float(ctx.scale_max), float(c.score)))
            w = weights[c.criterion_id]
            assessed_weight += w
            weighted += w * (c.score / ctx.scale_max)
    overall = round(100 * weighted / assessed_weight, 1) if assessed_weight else None
    return AIAssessment(
        score_scale_max=ctx.scale_max,
        overall_score=overall,
        assessed_weight=round(100 * assessed_weight / ctx.total_weight, 1),
        criteria=rubric.criteria,
        engine=engine,
        model=model,
    )
