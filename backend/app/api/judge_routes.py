"""Judge endpoints.

Workflow enforced server-side:
    open → (brief, no AI score) → submit independent evaluation
         → reveal AI assessment → keep or revise (with optional reason) → completed
The AI assessment is never included in any response before `submit`.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import AIReveal, FindingResponse, HumanEvaluation, JudgeAssignment, Revision, User, aware
from ..services.scoring import anchoring_metrics, validate_scores, weighted_score
from .deps import get_own_assignment, judge
from .serializers import (
    assignment_row,
    brief_out,
    criterion_out,
    document_out,
    evaluation_out,
    iso,
    reveal_out,
    revision_out,
)

router = APIRouter(prefix="/api/judge", tags=["judge"])


class CriterionScoreIn(BaseModel):
    criterion_id: int
    score: float
    comment: str = Field(default="", max_length=4000)


class SubmitIn(BaseModel):
    criterion_scores: list[CriterionScoreIn]
    overall_comment: str = Field(default="", max_length=8000)
    recommendation: Literal["advance", "discuss", "do_not_advance"] | None = None


class FindingIn(BaseModel):
    response: Literal["agree", "disagree", "unsure"]
    note: str = Field(default="", max_length=2000)


class FinalizeIn(BaseModel):
    decision: Literal["keep", "revise"]
    revised_scores: list[CriterionScoreIn] | None = None
    reason: str = Field(default="", max_length=4000)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/dashboard")
def dashboard(user: User = Depends(judge), db: Session = Depends(get_db)):
    rows = db.scalars(select(JudgeAssignment).where(JudgeAssignment.judge_id == user.id)
                      .order_by(JudgeAssignment.assigned_at)).all()
    items = [assignment_row(a) | {"round_name": a.submission.round.name} for a in rows]
    minutes = [i["review_minutes"] for i in items if i["review_minutes"] is not None]
    attention = [
        i for i in items
        if i["status"] != "completed" and (
            i["submission"]["integrity_status"] not in (None, "no_discrepancy_detected")
            or i["submission"]["analysis_status"] == "failed"
            or i["submission"]["status"] in ("processing_failed", "partially_processed")
        )
    ]
    return {
        "stats": {
            "assigned": len(items),
            "completed": sum(i["status"] == "completed" for i in items),
            "remaining": sum(i["status"] != "completed" for i in items),
            "in_progress": sum(i["status"] in ("in_progress", "submitted") for i in items),
            "avg_review_minutes": round(statistics.mean(minutes), 1) if minutes else None,
            "needs_attention": len(attention),
        },
        "assignments": items,
        "attention_ids": [i["id"] for i in attention],
    }


def _review_payload(a: JudgeAssignment) -> dict:
    sub = a.submission
    rnd = sub.round
    analysis = sub.latest_analysis
    return {
        "assignment": {
            "id": a.id,
            "status": a.status,
            "opened_at": iso(a.opened_at),
            "submitted_at": iso(a.submitted_at),
            "completed_at": iso(a.completed_at),
        },
        "submission": {
            "id": sub.id,
            "team_name": sub.team_name,
            "title": sub.title,
            "status": sub.status,
            "integrity_status": sub.integrity_status,
        },
        "round": {
            "id": rnd.id,
            "name": rnd.name,
            "score_scale_max": rnd.score_scale_max,
            "criteria": [criterion_out(c) for c in rnd.criteria],
        },
        "document": document_out(sub),
        # System-derived (not AI): available even when AI analysis fails.
        "integrity": (sub.evidence_pack or {}).get("integrity"),
        "not_assessed": (sub.evidence_pack or {}).get("not_assessed") or [],
        # Brief only — no scores. See reveal_out for the gated assessment.
        "analysis": brief_out(analysis),
        "evaluation": evaluation_out(a.evaluation),
        "finding_responses": {
            f.finding_key: {"response": f.response, "note": f.note, "updated_at": iso(f.updated_at)}
            for f in a.finding_responses
        },
        "reveal": reveal_out(a, analysis) if a.evaluation is not None else None,
        "revision": revision_out(a.revision),
    }


@router.get("/assignments/{assignment_id}")
def open_review(assignment_id: int, user: User = Depends(judge), db: Session = Depends(get_db)):
    a = get_own_assignment(db, assignment_id, user)
    if a.opened_at is None:
        a.opened_at = _now()
        a.status = "in_progress"
        audit.record(db, "review.opened", actor=user, round_id=a.round_id, submission_id=a.submission_id,
                     entity_type="assignment", entity_id=a.id)
        db.commit()
    return _review_payload(a)


@router.put("/assignments/{assignment_id}/findings/{finding_key}")
def respond_to_finding(assignment_id: int, finding_key: str, body: FindingIn,
                       user: User = Depends(judge), db: Session = Depends(get_db)):
    a = get_own_assignment(db, assignment_id, user)
    if a.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This evaluation is already complete.")
    if not finding_key or len(finding_key) > 80:
        raise HTTPException(422, "Invalid finding")
    existing = next((f for f in a.finding_responses if f.finding_key == finding_key), None)
    if existing:
        existing.response, existing.note, existing.updated_at = body.response, body.note.strip(), _now()
    else:
        a.finding_responses.append(FindingResponse(finding_key=finding_key, response=body.response, note=body.note.strip()))
    audit.record(db, "finding.responded", actor=user, round_id=a.round_id, submission_id=a.submission_id,
                 entity_type="assignment", entity_id=a.id,
                 details={"finding": finding_key, "response": body.response, "before_ai_reveal": a.reveal is None,
                          "note": body.note.strip()[:300]})
    db.commit()
    return {"finding_key": finding_key, "response": body.response, "note": body.note.strip()}


@router.post("/assignments/{assignment_id}/submit")
def submit_evaluation(assignment_id: int, body: SubmitIn, user: User = Depends(judge), db: Session = Depends(get_db)):
    a = get_own_assignment(db, assignment_id, user)
    if a.evaluation is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Evaluation already submitted.")
    rnd = a.submission.round
    try:
        scores = validate_scores([s.model_dump() for s in body.criterion_scores], rnd.criteria, rnd.score_scale_max)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    now = _now()
    a.evaluation = HumanEvaluation(
        criterion_scores=scores,
        weighted_score=weighted_score(scores, rnd.criteria, rnd.score_scale_max),
        overall_comment=body.overall_comment.strip(),
        recommendation=body.recommendation,
        submitted_at=now,
    )
    a.opened_at = a.opened_at or now
    a.submitted_at = now
    a.status = "submitted"
    audit.record(db, "evaluation.submitted", actor=user, round_id=a.round_id, submission_id=a.submission_id,
                 entity_type="assignment", entity_id=a.id,
                 details={"weighted_score": a.evaluation.weighted_score, "recommendation": body.recommendation,
                          "review_minutes": round((now - aware(a.opened_at)).total_seconds() / 60, 1)})
    db.commit()
    return _review_payload(a)


@router.post("/assignments/{assignment_id}/reveal")
def reveal_ai(assignment_id: int, user: User = Depends(judge), db: Session = Depends(get_db)):
    a = get_own_assignment(db, assignment_id, user)
    if a.evaluation is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Submit your own evaluation before viewing the AI assessment.")
    if a.reveal is None:
        analysis = a.submission.latest_analysis
        available = bool(analysis and analysis.status == "completed" and analysis.assessment_json)
        a.reveal = AIReveal(
            analysis_id=analysis.id if analysis else None,
            ai_available=available,
            ai_score_shown=analysis.ai_overall_score if available else None,
            revealed_at=_now(),
        )
        audit.record(db, "ai.revealed", actor=user, round_id=a.round_id, submission_id=a.submission_id,
                     entity_type="assignment", entity_id=a.id,
                     details={"ai_available": available, "ai_score_shown": a.reveal.ai_score_shown,
                              "human_initial_score": a.evaluation.weighted_score})
        db.commit()
    return _review_payload(a)


@router.post("/assignments/{assignment_id}/finalize")
def finalize(assignment_id: int, body: FinalizeIn, user: User = Depends(judge), db: Session = Depends(get_db)):
    a = get_own_assignment(db, assignment_id, user)
    if a.evaluation is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Submit your evaluation first.")
    if a.reveal is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Review the AI assessment before finishing.")
    if a.revision is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This evaluation is already complete.")
    rnd = a.submission.round
    initial_scores = a.evaluation.criterion_scores
    if body.decision == "revise":
        if not body.revised_scores:
            raise HTTPException(422, "Provide revised scores.")
        try:
            revised = validate_scores([s.model_dump() for s in body.revised_scores], rnd.criteria, rnd.score_scale_max)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    else:
        revised = initial_scores
    initial = a.evaluation.weighted_score
    revised_total = weighted_score(revised, rnd.criteria, rnd.score_scale_max)
    ai_score = a.reveal.ai_score_shown if a.reveal.ai_available else None
    analysis = a.submission.latest_analysis
    ai_criteria = None
    if a.reveal.ai_available and analysis and analysis.assessment_json:
        ai_criteria = [{"criterion_id": c["criterion_id"], "score": c.get("score")}
                       for c in analysis.assessment_json.get("criteria", [])]
    decision = "revised" if body.decision == "revise" and revised != initial_scores else "kept"
    metrics = anchoring_metrics(initial, ai_score, revised_total if decision == "revised" else initial)
    now = _now()
    a.revision = Revision(
        decision=decision,
        human_initial_score=initial,
        ai_score=ai_score,
        human_revised_score=revised_total if decision == "revised" else initial,
        revision_reason=body.reason.strip(),
        initial_criterion_scores=initial_scores,
        revised_criterion_scores=revised,
        ai_criterion_scores=ai_criteria,
        seconds_since_reveal=round((now - aware(a.reveal.revealed_at)).total_seconds(), 1),
        created_at=now,
        **metrics,
    )
    a.status = "completed"
    a.completed_at = now
    audit.record(db, f"evaluation.{decision}", actor=user, round_id=a.round_id, submission_id=a.submission_id,
                 entity_type="assignment", entity_id=a.id,
                 details={"human_initial_score": initial, "ai_score": ai_score,
                          "human_revised_score": a.revision.human_revised_score,
                          "revision_direction": metrics["revision_direction"],
                          "reason": body.reason.strip()[:500]})
    db.commit()
    return _review_payload(a)
