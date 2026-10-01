"""Response shaping. The AI assessment (scores) is only ever serialized by
`reveal_out`, which callers must gate on the judge having submitted."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import (
    AIAnalysis,
    AuditEvent,
    EvaluationRound,
    HumanEvaluation,
    JudgeAssignment,
    Revision,
    RubricCriterion,
    Slide,
    Submission,
    User,
    aware,
)
from ..services.processing import AI_FAILURE_MESSAGE, DOCUMENT_FAILURE_MESSAGE


def iso(dt: datetime | None) -> str | None:
    return aware(dt).isoformat() if dt else None


def user_out(u: User) -> dict[str, Any]:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "title": u.title,
            "organization": u.organization.name if u.organization else None}


def criterion_out(c: RubricCriterion) -> dict[str, Any]:
    return {"id": c.id, "name": c.name, "description": c.description, "weight": c.weight, "position": c.position}


def round_out(r: EvaluationRound, *, rubric_locked: bool | None = None) -> dict[str, Any]:
    out = {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "status": r.status,
        "score_scale_max": r.score_scale_max,
        "max_submissions": r.max_submissions,
        "max_file_size_mb": r.max_file_size_mb,
        "max_pages": r.max_pages,
        "allowed_file_types": r.allowed_file_types,
        "judges_per_submission": r.judges_per_submission,
        "created_at": iso(r.created_at),
        "criteria": [criterion_out(c) for c in r.criteria],
        "submission_count": len(r.submissions),
    }
    if rubric_locked is not None:
        out["rubric_locked"] = rubric_locked
    return out


def analysis_status_out(a: AIAnalysis | None) -> dict[str, Any]:
    if a is None:
        return {"status": "pending", "message": "AI analysis has not run yet."}
    out: dict[str, Any] = {
        "id": a.id,
        "status": a.status,
        "engine": a.engine,
        "model": a.model,
        "pipeline_version": a.pipeline_version,
        "completed_at": iso(a.completed_at),
    }
    if a.status == "failed":
        out["message"] = AI_FAILURE_MESSAGE
        out["error"] = a.error_message
    elif a.status in ("pending", "running"):
        out["message"] = "AI analysis in progress. Human review can begin."
    return out


def submission_summary(s: Submission) -> dict[str, Any]:
    f = s.primary_file
    a = s.latest_analysis
    pack = s.evidence_pack or {}
    return {
        "id": s.id,
        "round_id": s.round_id,
        "team_name": s.team_name,
        "title": s.title,
        "status": s.status,
        "processing_stage": s.processing_stage,
        "processing_error": s.processing_error,
        "integrity_status": s.integrity_status,
        "integrity_summary": (pack.get("integrity") or {}).get("summary"),
        "not_assessed_count": len(pack.get("not_assessed") or []),
        "analysis_status": a.status if a else "pending",
        "file": {
            "name": f.original_filename,
            "type": f.file_type,
            "size_bytes": f.size_bytes,
            "pages": f.page_count,
        } if f else None,
        "created_at": iso(s.created_at),
        "processed_at": iso(s.processed_at),
        "assignments": [
            {"id": x.id, "judge_id": x.judge_id, "judge_name": x.judge.name, "status": x.status}
            for x in s.assignments
        ],
    }


def slide_out(s: Slide) -> dict[str, Any]:
    return {
        "id": s.id,
        "slide_key": s.slide_key,
        "page_number": s.page_number,
        "title": s.title,
        "text": s.text,
        "speaker_notes": s.speaker_notes,
        "ocr_text": s.ocr_text,
        "ocr_status": s.ocr_status,
        "has_image": bool(s.image_path),
        "image_url": f"/api/slides/{s.id}/image" if s.image_path else None,
        "thumb_url": f"/api/slides/{s.id}/image?variant=thumb" if s.thumb_path else None,
        "has_visual_content": s.has_visual_content,
        "links": s.links or [],
        "integrity_flags": s.integrity_flags or [],
        "processing_notes": s.processing_notes or [],
    }


def document_out(s: Submission) -> dict[str, Any]:
    pack = s.evidence_pack or {}
    return {
        "slides": [slide_out(x) for x in s.slides],
        "file": {
            "name": s.primary_file.original_filename,
            "type": s.primary_file.file_type,
            "pages": s.primary_file.page_count,
            "download_url": f"/api/submissions/{s.id}/file",
        } if s.primary_file else None,
        "processing": {
            "status": s.status,
            "stage": s.processing_stage,
            "message": DOCUMENT_FAILURE_MESSAGE if s.status == "processing_failed" else None,
            "error": s.processing_error,
            "components": pack.get("ingestion") or {},
        },
    }


def brief_out(a: AIAnalysis | None) -> dict[str, Any]:
    """Judge-facing analysis payload. Deliberately excludes every score."""
    out = analysis_status_out(a)
    if a is not None and a.status == "completed" and a.brief_json:
        out["brief"] = a.brief_json
    return out


def evaluation_out(e: HumanEvaluation | None) -> dict[str, Any] | None:
    if e is None:
        return None
    return {
        "criterion_scores": e.criterion_scores,
        "weighted_score": e.weighted_score,
        "overall_comment": e.overall_comment,
        "recommendation": e.recommendation,
        "submitted_at": iso(e.submitted_at),
    }


def reveal_out(a: JudgeAssignment, analysis: AIAnalysis | None) -> dict[str, Any] | None:
    if a.reveal is None:
        return None
    base = {"revealed_at": iso(a.reveal.revealed_at), "ai_available": a.reveal.ai_available}
    if not a.reveal.ai_available or analysis is None or not analysis.assessment_json:
        return base | {"message": AI_FAILURE_MESSAGE}
    return base | {"assessment": analysis.assessment_json, "ai_score": analysis.ai_overall_score}


def revision_out(r: Revision | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return {
        "decision": r.decision,
        "human_initial_score": r.human_initial_score,
        "ai_score": r.ai_score,
        "human_revised_score": r.human_revised_score,
        "revision_reason": r.revision_reason,
        "initial_criterion_scores": r.initial_criterion_scores,
        "revised_criterion_scores": r.revised_criterion_scores,
        "initial_to_ai_difference": r.initial_to_ai_difference,
        "initial_to_revised_difference": r.initial_to_revised_difference,
        "revision_direction": r.revision_direction,
        "created_at": iso(r.created_at),
    }


def assignment_row(a: JudgeAssignment) -> dict[str, Any]:
    s = a.submission
    review_minutes = None
    if a.opened_at and a.submitted_at:
        review_minutes = round((aware(a.submitted_at) - aware(a.opened_at)).total_seconds() / 60, 1)
    brief = (s.latest_analysis.brief_json or {}) if s.latest_analysis else {}
    verify = brief.get("verify_these") or []
    return {
        "id": a.id,
        "status": a.status,
        "assigned_at": iso(a.assigned_at),
        "opened_at": iso(a.opened_at),
        "submitted_at": iso(a.submitted_at),
        "completed_at": iso(a.completed_at),
        "review_minutes": review_minutes,
        "submission": {
            "id": s.id,
            "team_name": s.team_name,
            "title": s.title,
            "status": s.status,
            "integrity_status": s.integrity_status,
            "file_type": s.primary_file.file_type if s.primary_file else None,
            "pages": s.primary_file.page_count if s.primary_file else None,
            "analysis_status": s.latest_analysis.status if s.latest_analysis else "pending",
            "verify_count": len(verify),
            "high_priority_count": sum(1 for v in verify if v.get("severity") == "high"),
            "not_assessed_count": len((s.evidence_pack or {}).get("not_assessed") or []),
        },
        "final_score": a.revision.human_revised_score if a.revision else None,
    }


def audit_out(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "action": e.action,
        "actor": e.actor_label,
        "actor_id": e.actor_id,
        "round_id": e.round_id,
        "submission_id": e.submission_id,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "details": e.details,
        "created_at": iso(e.created_at),
    }
