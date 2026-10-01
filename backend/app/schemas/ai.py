"""Structured AI output schemas.

Every stage of the AI pipeline returns one of these models. Model output is
validated against them (and grounded against the Evidence Pack) before it is
stored; the frontend renders only these structures, never free-form model text.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .evidence import IntegrityFlag, IntegrityStatus, NotAssessedItem

Severity = Literal["low", "medium", "high"]


class EvidenceRef(BaseModel):
    slide_id: str = Field(..., description="Stable unit id from the evidence pack, e.g. slide_05")
    excerpt: str = Field(..., description="Short verbatim excerpt from that slide supporting the point")
    # Filled in by the grounding step, never by the model.
    page_number: int | None = None
    verified: bool = False
    via: Literal["text", "speaker_notes", "ocr", "unknown"] = "unknown"


class Claim(BaseModel):
    id: str
    text: str
    category: Literal["quantitative", "technical", "market", "business", "impact", "novelty", "other"]
    evidence: list[EvidenceRef]
    supporting_evidence_found: bool = Field(
        ..., description="True only if the submission itself contains data/method backing the claim"
    )


class TopicEvidence(BaseModel):
    topic: str = Field(..., description="Machine key, e.g. problem, solution, architecture, impact")
    label: str = Field(..., description="Human label, e.g. 'Problem definition'")
    evidence: list[EvidenceRef]


# ---- Stage 1: Extractor -----------------------------------------------------


class ExtractionOutput(BaseModel):
    overview: str = Field(..., description="One or two neutral sentences: what is the team proposing?")
    target_users: str | None = None
    topics: list[TopicEvidence]
    claims: list[Claim]


# ---- Stage 2: Rubric analyzer ----------------------------------------------


class Issue(BaseModel):
    type: Literal[
        "unsupported_claim",
        "feasibility_gap",
        "missing_information",
        "potential_similarity",
        "inconsistency",
        "unclear",
    ]
    description: str
    severity: Severity


class CriterionAssessment(BaseModel):
    criterion_id: int
    criterion: str
    assessed: bool = Field(..., description="False if the evidence is insufficient to assess this criterion")
    finding: str
    evidence: list[EvidenceRef]
    issues: list[Issue]
    score: float | None = Field(None, description="Preliminary score on the round's scale; null if not assessed")
    not_assessed_reason: str | None = None


class RubricAnalysisOutput(BaseModel):
    criteria: list[CriterionAssessment]


# ---- Stage 3: Verifier / critic --------------------------------------------


class VerifyItem(BaseModel):
    id: str
    title: str = Field(..., description="Short headline, e.g. 'Claimed 40% cost reduction'")
    description: str
    type: Literal[
        "unsupported_claim",
        "feasibility_gap",
        "missing_information",
        "potential_similarity",
        "inconsistency",
        "integrity",
    ]
    severity: Severity
    evidence: list[EvidenceRef]
    label: str | None = Field(None, description="e.g. 'Potential similarity — human verification required.'")
    related_criteria: list[str] = Field(default_factory=list)


class VerificationOutput(BaseModel):
    items: list[VerifyItem]


# ---- Stage 4: Judge brief ---------------------------------------------------


class Strength(BaseModel):
    id: str
    text: str
    evidence: list[EvidenceRef]


class EvidenceHighlight(BaseModel):
    id: str
    label: str
    evidence: list[EvidenceRef]


class RubricCoverage(BaseModel):
    """Where the rubric is addressed — deliberately contains no judgement or score."""

    criterion_id: int
    criterion: str
    evidence: list[EvidenceRef]
    coverage: Literal["addressed", "limited", "not_found"]


class IntegritySummary(BaseModel):
    status: IntegrityStatus
    message: str
    flags: list[IntegrityFlag]
    limitations: str


class BriefProvenance(BaseModel):
    engine: str
    model: str | None
    pipeline_version: str
    stages: list[str]
    note: str


class JudgeBrief(BaseModel):
    overview: str
    target_users: str | None = None
    evidence_highlights: list[EvidenceHighlight]
    strengths: list[Strength]
    verify_these: list[VerifyItem]
    not_assessed: list[NotAssessedItem]
    integrity: IntegritySummary
    rubric_coverage: list[RubricCoverage]
    provenance: BriefProvenance


class BriefWriterOutput(BaseModel):
    """What the (LLM) brief generator is asked to produce; the rest is assembled by code."""

    overview: str
    strengths: list[Strength]
    verify_order: list[str] = Field(
        ..., description="Ids of verify items in priority order, most important first (max 6)"
    )


# ---- Hidden assessment (revealed only after human submission) --------------


class AIAssessment(BaseModel):
    label: Literal["AI-generated assessment — not a final decision."] = (
        "AI-generated assessment — not a final decision."
    )
    score_scale_max: int
    overall_score: float | None = Field(None, description="0-100 weighted, over assessed criteria only")
    assessed_weight: float = Field(..., description="Share of rubric weight (0-100) that could be assessed")
    criteria: list[CriterionAssessment]
    engine: str
    model: str | None
