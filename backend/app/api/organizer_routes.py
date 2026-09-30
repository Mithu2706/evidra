"""Organizer endpoints: rounds, rubric, submissions, judges, assignments,
progress, results and audit history."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..auth import hash_password
from ..db import get_db
from ..models import (
    AuditEvent,
    EvaluationRound,
    JudgeAssignment,
    RubricCriterion,
    Submission,
    SubmissionFile,
    User,
)
from ..services import processing, reporting, storage
from .deps import get_round_for, get_submission_for, organizer
from .serializers import (
    analysis_status_out,
    audit_out,
    brief_out,
    document_out,
    iso,
    round_out,
    submission_summary,
    user_out,
)

router = APIRouter(prefix="/api", tags=["organizer"])


# ---------------------------------------------------------------------------
# Rounds & rubric
# ---------------------------------------------------------------------------


class CriterionIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    weight: float = Field(gt=0, le=100)


def _check_weights(criteria: list[CriterionIn]) -> list[CriterionIn]:
    if not criteria:
        raise ValueError("Define at least one criterion")
    total = sum(c.weight for c in criteria)
    if abs(total - 100) > 0.01:
        raise ValueError(f"Criterion weights must add up to 100% (currently {total:g}%)")
    names = [c.name.strip().lower() for c in criteria]
    if len(set(names)) != len(names):
        raise ValueError("Criterion names must be unique")
    return criteria


class RoundIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    score_scale_max: int = Field(default=10, ge=3, le=100)
    max_submissions: int | None = Field(default=None, ge=1, le=10000)
    max_file_size_mb: int = Field(default=25, ge=1, le=200)
    max_pages: int = Field(default=30, ge=1, le=300)
    allowed_file_types: list[str] = Field(default_factory=lambda: ["pdf", "pptx"])
    judges_per_submission: int = Field(default=2, ge=1, le=10)
    criteria: list[CriterionIn]

    @field_validator("criteria")
    @classmethod
    def _weights(cls, v):
        return _check_weights(v)

    @field_validator("allowed_file_types")
    @classmethod
    def _types(cls, v):
        v = sorted({t.lower().lstrip(".") for t in v})
        if not v or any(t not in ("pdf", "pptx") for t in v):
            raise ValueError("Allowed file types are pdf and pptx")
        return v


class RoundPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, pattern="^(draft|open|closed)$")
    max_submissions: int | None = Field(default=None, ge=1)
    max_file_size_mb: int | None = Field(default=None, ge=1, le=200)
    max_pages: int | None = Field(default=None, ge=1, le=300)
    judges_per_submission: int | None = Field(default=None, ge=1, le=10)


class CriteriaIn(BaseModel):
    criteria: list[CriterionIn]

    @field_validator("criteria")
    @classmethod
    def _weights(cls, v):
        return _check_weights(v)


def _rubric_locked(rnd: EvaluationRound) -> bool:
    return any(a.status in ("submitted", "completed") for s in rnd.submissions for a in s.assignments)


@router.get("/rounds")
def list_rounds(user: User = Depends(organizer), db: Session = Depends(get_db)):
    rounds = db.scalars(
        select(EvaluationRound)
        .where(EvaluationRound.organization_id == user.organization_id)
        .order_by(EvaluationRound.created_at.desc())
    ).all()
    return [round_out(r) for r in rounds]


@router.post("/rounds", status_code=201)
def create_round(body: RoundIn, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = EvaluationRound(
        organization_id=user.organization_id,
        created_by_id=user.id,
        **body.model_dump(exclude={"criteria"}),
    )
    rnd.criteria = [
        RubricCriterion(name=c.name.strip(), description=c.description.strip(), weight=c.weight, position=i)
        for i, c in enumerate(body.criteria)
    ]
    db.add(rnd)
    db.flush()
    audit.record(db, "round.created", actor=user, round_id=rnd.id, entity_type="round", entity_id=rnd.id,
                 details={"name": rnd.name, "criteria": [{"name": c.name, "weight": c.weight} for c in body.criteria]})
    db.commit()
    return round_out(rnd, rubric_locked=False)


@router.get("/rounds/{round_id}")
def get_round(round_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    return round_out(rnd, rubric_locked=_rubric_locked(rnd))


@router.patch("/rounds/{round_id}")
def update_round(round_id: int, body: RoundPatch, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(rnd, key, value)
    audit.record(db, "round.updated", actor=user, round_id=rnd.id, entity_type="round", entity_id=rnd.id,
                 details={"changes": changes})
    db.commit()
    return round_out(rnd, rubric_locked=_rubric_locked(rnd))


@router.put("/rounds/{round_id}/criteria")
def replace_criteria(round_id: int, body: CriteriaIn, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    if _rubric_locked(rnd):
        raise HTTPException(status.HTTP_409_CONFLICT, "The rubric is locked because judges have already submitted evaluations.")
    before = [{"name": c.name, "weight": c.weight} for c in rnd.criteria]
    rnd.criteria.clear()
    db.flush()
    rnd.criteria.extend(
        RubricCriterion(name=c.name.strip(), description=c.description.strip(), weight=c.weight, position=i)
        for i, c in enumerate(body.criteria)
    )
    audit.record(db, "rubric.updated", actor=user, round_id=rnd.id, entity_type="round", entity_id=rnd.id,
                 details={"before": before, "after": [{"name": c.name, "weight": c.weight} for c in body.criteria]})
    db.commit()
    # Briefs reference the rubric; refresh analyses for processed submissions.
    for s in rnd.submissions:
        if s.evidence_pack is not None:
            processing.enqueue_analysis(s.id)
    return round_out(rnd, rubric_locked=False)


@router.get("/rounds/{round_id}/dashboard")
def round_dashboard(round_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    return {"round": round_out(rnd, rubric_locked=_rubric_locked(rnd))} | reporting.dashboard(db, rnd)


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------


@router.get("/rounds/{round_id}/submissions")
def list_submissions(round_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    return [submission_summary(s) | {"stage": reporting.submission_stage(s)}
            for s in sorted(rnd.submissions, key=lambda s: s.created_at)]


@router.post("/rounds/{round_id}/submissions", status_code=201)
def upload_submission(
    round_id: int,
    file: UploadFile = File(...),
    team_name: str = Form(..., min_length=1, max_length=200),
    title: str = Form(default="", max_length=300),
    user: User = Depends(organizer),
    db: Session = Depends(get_db),
):
    rnd = get_round_for(db, round_id, user)
    if rnd.status == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "This round is closed to new submissions.")
    if rnd.max_submissions and len(rnd.submissions) >= rnd.max_submissions:
        raise HTTPException(status.HTTP_409_CONFLICT, f"This round accepts at most {rnd.max_submissions} submissions.")
    filename = Path(file.filename or "submission").name[:300]
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in (rnd.allowed_file_types or ["pdf", "pptx"]):
        raise HTTPException(422,
                            f"Unsupported file type. Allowed: {', '.join(rnd.allowed_file_types)}.")

    sub = Submission(round_id=rnd.id, team_name=team_name.strip(), title=(title or Path(filename).stem).strip(),
                     status="uploaded", uploaded_by_id=user.id)
    db.add(sub)
    db.flush()
    path, size, digest = storage.save_upload(sub.id, file.file, filename)
    if size > rnd.max_file_size_mb * 1024 * 1024:
        path.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"File exceeds the {rnd.max_file_size_mb} MB limit for this round.")
    db.add(SubmissionFile(submission_id=sub.id, original_filename=filename, stored_path=str(path),
                          file_type=ext, size_bytes=size, sha256=digest))
    duplicate = db.scalar(
        select(SubmissionFile).join(Submission)
        .where(Submission.round_id == rnd.id, SubmissionFile.sha256 == digest, Submission.id != sub.id)
    )
    audit.record(db, "submission.uploaded", actor=user, round_id=rnd.id, submission_id=sub.id,
                 entity_type="submission", entity_id=sub.id,
                 details={"filename": filename, "size_bytes": size, "sha256": digest,
                          "duplicate_of": duplicate.submission_id if duplicate else None})
    db.commit()
    processing.enqueue_processing(sub.id)
    return submission_summary(sub) | {"duplicate_of": duplicate.submission_id if duplicate else None}


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    sub = get_submission_for(db, submission_id, user)
    pack = sub.evidence_pack or {}
    complete = bool(sub.assignments) and all(a.status == "completed" for a in sub.assignments)
    analysis = sub.latest_analysis
    return {
        "submission": submission_summary(sub) | {"stage": reporting.submission_stage(sub)},
        "document": document_out(sub),
        "analysis": brief_out(analysis),
        "integrity": pack.get("integrity"),
        "not_assessed": pack.get("not_assessed") or [],
        "judging_complete": complete,
        "ai_assessment": analysis.assessment_json if complete and analysis and analysis.status == "completed" else None,
        "assignments": [
            {
                "id": a.id,
                "judge": user_out(a.judge),
                "status": a.status,
                "opened_at": iso(a.opened_at),
                "submitted_at": iso(a.submitted_at),
                "completed_at": iso(a.completed_at),
                # Individual judge scores are visible to organizers only once judging is complete.
                "final_score": a.revision.human_revised_score if complete and a.revision else None,
                "decision": a.revision.decision if complete and a.revision else None,
            }
            for a in sub.assignments
        ],
        "analysis_history": [analysis_status_out(x) for x in sub.analyses],
    }


@router.post("/submissions/{submission_id}/reprocess", status_code=202)
def reprocess(submission_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    sub = get_submission_for(db, submission_id, user)
    if any(a.status in ("submitted", "completed") for a in sub.assignments):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Judges have already evaluated this submission; reprocessing would change their brief.")
    if sub.status == "processing":
        raise HTTPException(status.HTTP_409_CONFLICT, "Submission is already being processed.")
    sub.status, sub.processing_stage = "processing", "queued"
    audit.record(db, "submission.reprocess_requested", actor=user, round_id=sub.round_id, submission_id=sub.id,
                 entity_type="submission", entity_id=sub.id)
    db.commit()
    processing.enqueue_processing(sub.id)
    return {"status": "queued"}


# ---------------------------------------------------------------------------
# Judges & assignments
# ---------------------------------------------------------------------------


class JudgeIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    title: str | None = Field(default=None, max_length=200)


class AssignmentIn(BaseModel):
    submission_id: int
    judge_id: int


class AutoAssignIn(BaseModel):
    judges_per_submission: int | None = Field(default=None, ge=1, le=10)
    judge_ids: list[int] | None = None


@router.get("/rounds/{round_id}/judges")
def list_judges(round_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    judges = db.scalars(select(User).where(User.organization_id == user.organization_id, User.role == "judge")
                        .order_by(User.name)).all()
    counts: dict[int, dict[str, int]] = {}
    for s in rnd.submissions:
        for a in s.assignments:
            c = counts.setdefault(a.judge_id, {"assigned": 0, "completed": 0})
            c["assigned"] += 1
            c["completed"] += a.status == "completed"
    return [user_out(j) | counts.get(j.id, {"assigned": 0, "completed": 0}) for j in judges]


@router.post("/rounds/{round_id}/judges", status_code=201)
def add_judge(round_id: int, body: JudgeIn, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    temp_password = secrets.token_urlsafe(9)
    judge = User(organization_id=user.organization_id, email=body.email.lower(), name=body.name.strip(),
                 title=body.title, role="judge", password_hash=hash_password(temp_password))
    db.add(judge)
    db.flush()
    audit.record(db, "judge.invited", actor=user, round_id=rnd.id, entity_type="user", entity_id=judge.id,
                 details={"email": judge.email})
    db.commit()
    return user_out(judge) | {"temporary_password": temp_password, "assigned": 0, "completed": 0}


def _create_assignment(db: Session, rnd: EvaluationRound, sub: Submission, judge: User, actor: User) -> JudgeAssignment:
    a = JudgeAssignment(round_id=rnd.id, submission_id=sub.id, judge_id=judge.id, assigned_by_id=actor.id)
    db.add(a)
    db.flush()
    audit.record(db, "assignment.created", actor=actor, round_id=rnd.id, submission_id=sub.id,
                 entity_type="assignment", entity_id=a.id, details={"judge": judge.name})
    return a


@router.post("/rounds/{round_id}/assignments", status_code=201)
def assign(round_id: int, body: AssignmentIn, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    sub = db.get(Submission, body.submission_id)
    judge = db.get(User, body.judge_id)
    if sub is None or sub.round_id != rnd.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    if judge is None or judge.role != "judge" or judge.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Judge not found")
    if any(a.judge_id == judge.id for a in sub.assignments):
        raise HTTPException(status.HTTP_409_CONFLICT, "Judge is already assigned to this submission")
    a = _create_assignment(db, rnd, sub, judge, user)
    db.commit()
    return {"id": a.id, "status": a.status}


@router.post("/rounds/{round_id}/assignments/auto")
def auto_assign(round_id: int, body: AutoAssignIn, user: User = Depends(organizer), db: Session = Depends(get_db)):
    """Balanced assignment: fill each submission up to N judges, least-loaded judges first."""
    rnd = get_round_for(db, round_id, user)
    per = body.judges_per_submission or rnd.judges_per_submission
    query = select(User).where(User.organization_id == user.organization_id, User.role == "judge", User.is_active)
    if body.judge_ids:
        query = query.where(User.id.in_(body.judge_ids))
    judges = db.scalars(query.order_by(User.id)).all()
    if not judges:
        raise HTTPException(status.HTTP_409_CONFLICT, "No judges available")
    load = {j.id: 0 for j in judges}
    for s in rnd.submissions:
        for a in s.assignments:
            if a.judge_id in load:
                load[a.judge_id] += 1
    created = 0
    for s in sorted(rnd.submissions, key=lambda x: x.id):
        taken = {a.judge_id for a in s.assignments}
        while len(taken) < per:
            candidates = [j for j in judges if j.id not in taken]
            if not candidates:
                break
            j = min(candidates, key=lambda x: (load[x.id], x.id))
            _create_assignment(db, rnd, s, j, user)
            taken.add(j.id)
            load[j.id] += 1
            created += 1
    db.commit()
    return {"created": created}


@router.delete("/assignments/{assignment_id}", status_code=204)
def unassign(assignment_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    a = db.get(JudgeAssignment, assignment_id)
    if a is None or a.submission.round.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    if a.status != "assigned":
        raise HTTPException(status.HTTP_409_CONFLICT, "The judge has already started this review.")
    audit.record(db, "assignment.removed", actor=user, round_id=a.round_id, submission_id=a.submission_id,
                 entity_type="assignment", entity_id=a.id, details={"judge": a.judge.name})
    db.delete(a)
    db.commit()


# ---------------------------------------------------------------------------
# Results & audit
# ---------------------------------------------------------------------------


@router.get("/rounds/{round_id}/results")
def round_results(round_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    return reporting.results(rnd)


@router.get("/rounds/{round_id}/results/anchoring.csv", response_class=PlainTextResponse)
def anchoring_export(round_id: int, user: User = Depends(organizer), db: Session = Depends(get_db)):
    rnd = get_round_for(db, round_id, user)
    audit.record(db, "results.exported", actor=user, round_id=rnd.id, entity_type="round", entity_id=rnd.id)
    db.commit()
    return PlainTextResponse(
        reporting.anchoring_csv(db, rnd),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="evidra-round-{rnd.id}-anchoring.csv"'},
    )


@router.get("/rounds/{round_id}/audit")
def round_audit(
    round_id: int,
    submission_id: int | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(organizer),
    db: Session = Depends(get_db),
):
    rnd = get_round_for(db, round_id, user)
    q = select(AuditEvent).where(AuditEvent.round_id == rnd.id)
    if submission_id:
        q = q.where(AuditEvent.submission_id == submission_id)
    if action:
        q = q.where(AuditEvent.action.like(f"{action}%"))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    events = db.scalars(q.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).offset(offset).limit(limit)).all()
    return {"total": total, "events": [audit_out(e) for e in events]}
