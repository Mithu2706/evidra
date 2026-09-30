"""Relational data model.

Design notes
------------
* A judge's *initial* evaluation (HumanEvaluation) is immutable once submitted.
  Anything that happens after the AI reveal is stored separately (AIReveal,
  Revision) so the anchoring study can compare "before AI" and "after AI".
* AIAnalysis keeps the judge-facing brief (`brief_json`) apart from the
  scored assessment (`assessment_json`, `ai_overall_score`). The API layer only
  releases the assessment after the judge has submitted.
* Evidence rows carry a generic `source_type` / `source_location` pair so that
  future sources (GitHub, video, website) fit the same model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo on read; all stored timestamps are UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))

    users: Mapped[list[User]] = relationship(back_populates="organization")
    rounds: Mapped[list[EvaluationRound]] = relationship(back_populates="organization")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # organizer | judge
    title: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped[Organization] = relationship(back_populates="users")


class EvaluationRound(TimestampMixin, Base):
    __tablename__ = "evaluation_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # draft|open|closed
    score_scale_max: Mapped[int] = mapped_column(Integer, default=10)
    max_submissions: Mapped[int | None] = mapped_column(Integer)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=25)
    max_pages: Mapped[int] = mapped_column(Integer, default=30)
    allowed_file_types: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["pdf", "pptx"])
    judges_per_submission: Mapped[int] = mapped_column(Integer, default=2)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    organization: Mapped[Organization] = relationship(back_populates="rounds")
    criteria: Mapped[list[RubricCriterion]] = relationship(
        back_populates="round",
        order_by="RubricCriterion.position",
        cascade="all, delete-orphan",
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="round", cascade="all, delete-orphan"
    )


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("evaluation_rounds.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    weight: Mapped[float] = mapped_column(Float)  # percentage, criteria sum to 100
    position: Mapped[int] = mapped_column(Integer, default=0)

    round: Mapped[EvaluationRound] = relationship(back_populates="criteria")


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("evaluation_rounds.id"), index=True)
    team_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    # uploaded | processing | ready | partially_processed | processing_failed
    status: Mapped[str] = mapped_column(String(30), default="uploaded")
    processing_stage: Mapped[str | None] = mapped_column(String(60))
    processing_error: Mapped[str | None] = mapped_column(Text)
    # no_discrepancy_detected | potential_discrepancy |
    # suspicious_instruction_detected | manual_review_required
    integrity_status: Mapped[str | None] = mapped_column(String(40))
    evidence_pack: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    round: Mapped[EvaluationRound] = relationship(back_populates="submissions")
    files: Mapped[list[SubmissionFile]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )
    slides: Mapped[list[Slide]] = relationship(
        back_populates="submission", order_by="Slide.page_number", cascade="all, delete-orphan"
    )
    analyses: Mapped[list[AIAnalysis]] = relationship(
        back_populates="submission", order_by="AIAnalysis.id", cascade="all, delete-orphan"
    )
    assignments: Mapped[list[JudgeAssignment]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )

    @property
    def primary_file(self) -> SubmissionFile | None:
        return self.files[0] if self.files else None

    @property
    def latest_analysis(self) -> AIAnalysis | None:
        return self.analyses[-1] if self.analyses else None


class SubmissionFile(TimestampMixin, Base):
    __tablename__ = "submission_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(400))
    stored_path: Mapped[str] = mapped_column(String(1000))
    file_type: Mapped[str] = mapped_column(String(20))  # pdf | pptx
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer)
    rendered_pdf_path: Mapped[str | None] = mapped_column(String(1000))

    submission: Mapped[Submission] = relationship(back_populates="files")


class Slide(Base):
    """One page/slide of a submission — the atomic unit evidence points to."""

    __tablename__ = "slides"
    __table_args__ = (UniqueConstraint("submission_id", "slide_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    slide_key: Mapped[str] = mapped_column(String(40))  # stable id, e.g. "slide_06"
    page_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text, default="")
    speaker_notes: Mapped[str | None] = mapped_column(Text)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_status: Mapped[str] = mapped_column(String(30), default="not_run")
    image_path: Mapped[str | None] = mapped_column(String(1000))
    thumb_path: Mapped[str | None] = mapped_column(String(1000))
    has_visual_content: Mapped[bool] = mapped_column(Boolean, default=False)
    links: Mapped[list[str]] = mapped_column(JSON, default=list)
    integrity_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    processing_notes: Mapped[list[str]] = mapped_column(JSON, default=list)

    submission: Mapped[Submission] = relationship(back_populates="slides")


class AIAnalysis(TimestampMixin, Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|completed|failed
    engine: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(100))
    pipeline_version: Mapped[str] = mapped_column(String(20))
    extraction_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    verification_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    brief_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Hidden from judges until they submit their own evaluation.
    assessment_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ai_overall_score: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    submission: Mapped[Submission] = relationship(back_populates="analyses")
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class Evidence(Base):
    """A grounded reference from an AI finding to a location in a source."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analyses.id"), index=True)
    finding_key: Mapped[str] = mapped_column(String(80))  # e.g. "verify:v2"
    # slide | document | github | video | website
    source_type: Mapped[str] = mapped_column(String(20), default="slide")
    # {"kind": "slide_number"|"page_number"|"file_path"|"timestamp"|"url", "value": ...}
    source_location: Mapped[dict[str, Any]] = mapped_column(JSON)
    slide_id: Mapped[int | None] = mapped_column(ForeignKey("slides.id"))
    excerpt: Mapped[str] = mapped_column(Text, default="")
    excerpt_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    analysis: Mapped[AIAnalysis] = relationship(back_populates="evidence")


class JudgeAssignment(Base):
    __tablename__ = "judge_assignments"
    __table_args__ = (UniqueConstraint("submission_id", "judge_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("evaluation_rounds.id"), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # assigned | in_progress | submitted | completed
    status: Mapped[str] = mapped_column(String(20), default="assigned")
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    submission: Mapped[Submission] = relationship(back_populates="assignments")
    judge: Mapped[User] = relationship(foreign_keys=[judge_id])
    evaluation: Mapped[HumanEvaluation | None] = relationship(
        back_populates="assignment", uselist=False, cascade="all, delete-orphan"
    )
    reveal: Mapped[AIReveal | None] = relationship(
        back_populates="assignment", uselist=False, cascade="all, delete-orphan"
    )
    revision: Mapped[Revision | None] = relationship(
        back_populates="assignment", uselist=False, cascade="all, delete-orphan"
    )
    finding_responses: Mapped[list[FindingResponse]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class HumanEvaluation(Base):
    """The judge's independent evaluation, captured *before* any AI score is shown."""

    __tablename__ = "human_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("judge_assignments.id"), unique=True)
    # [{"criterion_id": 1, "score": 7, "comment": "..."}]
    criterion_scores: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    weighted_score: Mapped[float] = mapped_column(Float)  # 0-100
    overall_comment: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str | None] = mapped_column(String(30))  # advance|discuss|do_not_advance
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped[JudgeAssignment] = relationship(back_populates="evaluation")


class FindingResponse(Base):
    """A judge agreeing / disagreeing with an individual AI finding."""

    __tablename__ = "finding_responses"
    __table_args__ = (UniqueConstraint("assignment_id", "finding_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("judge_assignments.id"), index=True)
    finding_key: Mapped[str] = mapped_column(String(80))
    response: Mapped[str] = mapped_column(String(20))  # agree | disagree | unsure
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped[JudgeAssignment] = relationship(back_populates="finding_responses")


class AIReveal(Base):
    __tablename__ = "ai_reveals"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("judge_assignments.id"), unique=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("ai_analyses.id"))
    ai_available: Mapped[bool] = mapped_column(Boolean)
    ai_score_shown: Mapped[float | None] = mapped_column(Float)
    revealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped[JudgeAssignment] = relationship(back_populates="reveal")


class Revision(Base):
    """Post-reveal decision record — the core row of the anchoring dataset."""

    __tablename__ = "revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("judge_assignments.id"), unique=True)
    decision: Mapped[str] = mapped_column(String(20))  # kept | revised
    human_initial_score: Mapped[float] = mapped_column(Float)
    ai_score: Mapped[float | None] = mapped_column(Float)
    human_revised_score: Mapped[float] = mapped_column(Float)
    revision_reason: Mapped[str] = mapped_column(Text, default="")
    initial_criterion_scores: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    revised_criterion_scores: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    ai_criterion_scores: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    initial_to_ai_difference: Mapped[float | None] = mapped_column(Float)
    initial_to_revised_difference: Mapped[float] = mapped_column(Float)
    # no_change | toward_ai | away_from_ai | ai_unavailable
    revision_direction: Mapped[str] = mapped_column(String(20))
    seconds_since_reveal: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    assignment: Mapped[JudgeAssignment] = relationship(back_populates="revision")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    round_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_rounds.id"), index=True)
    submission_id: Mapped[int | None] = mapped_column(Integer, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_label: Mapped[str] = mapped_column(String(200))  # "Dana Okafor (organizer)" / "system"
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
