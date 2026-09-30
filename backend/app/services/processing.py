"""Background processing: ingestion → Evidence Pack → AI analysis.

Runs in a small in-process worker pool. A production deployment would move
this to a job queue; the functions are written to be queue-friendly (they
take ids, open their own DB session and are safe to re-run).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import audit
from ..ai.context import AnalysisContext, CriterionSpec
from ..ai.pipeline import PIPELINE_VERSION, AnalysisFailed, AnalysisPipeline, build_pipeline
from ..config import get_settings
from ..db import SessionLocal
from ..ingestion.base import IngestionError
from ..ingestion.pipeline import IngestionPipeline
from ..ingestion.validation import SubmissionLimits, ValidationFailed
from ..models import AIAnalysis, Evidence, Slide, Submission
from ..schemas.ai import EvidenceRef
from ..schemas.evidence import EvidencePack
from . import storage

log = logging.getLogger(__name__)

DOCUMENT_FAILURE_MESSAGE = "Document could not be fully processed. Manual review required."
AI_FAILURE_MESSAGE = "AI analysis unavailable. Human review can continue."

_executor: ThreadPoolExecutor | None = None
_ingestion: IngestionPipeline | None = None


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=get_settings().processing_workers, thread_name_prefix="evidra")
    return _executor


def ingestion_pipeline() -> IngestionPipeline:
    global _ingestion
    if _ingestion is None:
        s = get_settings()
        _ingestion = IngestionPipeline(ocr_preference=s.ocr_engine, render_width_px=s.render_width_px)
    return _ingestion


def enqueue_processing(submission_id: int) -> None:
    _pool().submit(_safe, process_submission, submission_id)


def enqueue_analysis(submission_id: int) -> None:
    _pool().submit(_safe, analyze_submission, submission_id)


def _safe(fn, submission_id: int) -> None:
    try:
        fn(submission_id)
    except Exception:  # never let a worker die silently
        log.exception("Processing crashed for submission %s", submission_id)


# ---------------------------------------------------------------------------


def process_submission(submission_id: int, *, pipeline: AnalysisPipeline | None = None) -> None:
    db = SessionLocal()
    try:
        sub = db.get(Submission, submission_id)
        if sub is None or not sub.files:
            return
        file = sub.primary_file
        rnd = sub.round
        sub.status, sub.processing_stage, sub.processing_error = "processing", "queued", None
        audit.record(db, "submission.ingestion_started", organization_id=rnd.organization_id,
                     round_id=rnd.id, submission_id=sub.id, entity_type="submission", entity_id=sub.id)
        db.commit()

        def on_stage(stage: str) -> None:
            sub.processing_stage = stage
            db.commit()

        limits = SubmissionLimits(
            max_file_size_mb=rnd.max_file_size_mb,
            max_pages=rnd.max_pages,
            allowed_file_types=tuple(rnd.allowed_file_types or ("pdf", "pptx")),
        )
        try:
            result = ingestion_pipeline().run(
                Path(file.stored_path),
                original_filename=file.original_filename,
                submission_id=sub.id,
                limits=limits,
                work_dir=storage.reset_work_dir(sub.id),
                on_stage=on_stage,
            )
        except (ValidationFailed, IngestionError) as exc:
            _fail_ingestion(db, sub, str(exc))
            return
        except Exception as exc:
            log.exception("Unexpected ingestion failure")
            _fail_ingestion(db, sub, f"Unexpected error: {type(exc).__name__}")
            return

        pack = result.pack
        db.execute(delete(Slide).where(Slide.submission_id == sub.id))
        for unit, page in zip(pack.units, result.rendered):
            db.add(
                Slide(
                    submission_id=sub.id,
                    slide_key=unit.slide_id,
                    page_number=unit.page_number,
                    title=unit.title,
                    text=unit.text,
                    speaker_notes=unit.speaker_notes,
                    ocr_text=unit.ocr_text,
                    ocr_status=unit.ocr_status,
                    image_path=str(page.image_path) if page.image_path else None,
                    thumb_path=str(page.thumb_path) if page.thumb_path else None,
                    has_visual_content=unit.has_visual_content,
                    links=unit.links,
                    integrity_flags=[f.model_dump() for f in unit.integrity_flags],
                    processing_notes=unit.processing_notes,
                )
            )
        file.page_count = pack.page_count
        file.rendered_pdf_path = str(result.renderable_pdf) if result.renderable_pdf else None
        sub.evidence_pack = pack.model_dump(mode="json")
        sub.integrity_status = pack.integrity.status
        sub.status = "partially_processed" if pack.processing_status == "partial" else "ready"
        sub.processing_stage = None
        sub.processed_at = datetime.now(timezone.utc)
        audit.record(
            db, "submission.ingested", organization_id=rnd.organization_id, round_id=rnd.id,
            submission_id=sub.id, entity_type="submission", entity_id=sub.id,
            details={
                "pages": pack.page_count,
                "processing_status": pack.processing_status,
                "integrity_status": pack.integrity.status,
                "not_assessed_items": len(pack.not_assessed),
                "components": pack.ingestion,
            },
        )
        if pack.integrity.status != "no_discrepancy_detected":
            audit.record(
                db, "integrity.flagged", organization_id=rnd.organization_id, round_id=rnd.id,
                submission_id=sub.id, entity_type="submission", entity_id=sub.id,
                details={"status": pack.integrity.status, "summary": pack.integrity.summary},
            )
        db.commit()
        _run_analysis(db, sub, pipeline)
    finally:
        db.close()


def _fail_ingestion(db: Session, sub: Submission, detail: str) -> None:
    sub.status = "processing_failed"
    sub.processing_stage = None
    sub.processing_error = f"{DOCUMENT_FAILURE_MESSAGE} ({detail})"
    sub.integrity_status = "manual_review_required"
    sub.processed_at = datetime.now(timezone.utc)
    audit.record(
        db, "submission.ingestion_failed", organization_id=sub.round.organization_id, round_id=sub.round_id,
        submission_id=sub.id, entity_type="submission", entity_id=sub.id, details={"error": detail},
    )
    db.commit()


def analyze_submission(submission_id: int, *, pipeline: AnalysisPipeline | None = None) -> None:
    db = SessionLocal()
    try:
        sub = db.get(Submission, submission_id)
        if sub is None or sub.evidence_pack is None:
            return
        _run_analysis(db, sub, pipeline)
    finally:
        db.close()


def _run_analysis(db: Session, sub: Submission, pipeline: AnalysisPipeline | None) -> AIAnalysis:
    settings = get_settings()
    rnd = sub.round
    analysis = AIAnalysis(
        submission_id=sub.id,
        status="running",
        engine=settings.ai_engine if pipeline is None else pipeline.engine,
        model=settings.anthropic_model if settings.ai_engine == "anthropic" else None,
        pipeline_version=PIPELINE_VERSION,
        started_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    sub.processing_stage = "ai_analysis"
    db.commit()

    try:
        pipeline = pipeline or build_pipeline(settings)
        analysis.engine, analysis.model = pipeline.engine, pipeline.model
        ctx = AnalysisContext(
            pack=EvidencePack.model_validate(sub.evidence_pack),
            criteria=[CriterionSpec(c.id, c.name, c.description, c.weight) for c in rnd.criteria],
            scale_max=rnd.score_scale_max,
            team_name=sub.team_name,
            submission_title=sub.title,
            round_name=rnd.name,
        )
        result = pipeline.run(ctx)
    except (AnalysisFailed, Exception) as exc:  # includes provider misconfiguration
        analysis.status = "failed"
        analysis.error_message = str(exc)[:1000]
        analysis.completed_at = datetime.now(timezone.utc)
        sub.processing_stage = None
        audit.record(
            db, "analysis.failed", organization_id=rnd.organization_id, round_id=rnd.id,
            submission_id=sub.id, entity_type="ai_analysis", entity_id=analysis.id,
            details={"engine": analysis.engine, "error": analysis.error_message},
        )
        db.commit()
        return analysis

    analysis.extraction_json = result.extraction.model_dump(mode="json")
    analysis.verification_json = result.verification.model_dump(mode="json")
    analysis.brief_json = result.brief.model_dump(mode="json")
    analysis.assessment_json = result.assessment.model_dump(mode="json")
    analysis.ai_overall_score = result.assessment.overall_score
    analysis.status = "completed"
    analysis.completed_at = datetime.now(timezone.utc)
    db.flush()
    _store_evidence(db, sub, analysis, result)
    sub.processing_stage = None
    audit.record(
        db, "analysis.completed", organization_id=rnd.organization_id, round_id=rnd.id,
        submission_id=sub.id, entity_type="ai_analysis", entity_id=analysis.id,
        details={
            "engine": analysis.engine,
            "model": analysis.model,
            "verify_items": len(result.brief.verify_these),
            "strengths": len(result.brief.strengths),
        },
    )
    db.commit()
    return analysis


def _store_evidence(db: Session, sub: Submission, analysis: AIAnalysis, result) -> None:
    slide_ids = {s.slide_key: s.id for s in sub.slides}
    kind = "slide_number" if sub.primary_file and sub.primary_file.file_type == "pptx" else "page_number"

    def add(key: str, refs: list[EvidenceRef]) -> None:
        for ref in refs:
            db.add(
                Evidence(
                    submission_id=sub.id,
                    analysis_id=analysis.id,
                    finding_key=key,
                    source_type="slide",
                    source_location={"kind": kind, "value": ref.page_number},
                    slide_id=slide_ids.get(ref.slide_id),
                    excerpt=ref.excerpt,
                    excerpt_verified=ref.verified,
                )
            )

    brief = result.brief
    for h in brief.evidence_highlights:
        add(f"evidence:{h.id}", h.evidence)
    for s in brief.strengths:
        add(f"strength:{s.id}", s.evidence)
    for v in brief.verify_these:
        add(f"verify:{v.id}", v.evidence)
    for c in result.assessment.criteria:
        add(f"criterion:{c.criterion_id}", c.evidence)
