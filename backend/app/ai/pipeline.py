"""AI analysis pipeline: Extractor → Rubric Analyzer → Verifier → Brief Generator.

The pipeline validates and grounds every stage's output against the Evidence
Pack before the next stage sees it. Any failure aborts the whole analysis —
partial or fabricated results are never stored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import Settings
from ..schemas.ai import (
    AIAssessment,
    BriefProvenance,
    ExtractionOutput,
    JudgeBrief,
    RubricAnalysisOutput,
    VerificationOutput,
)
from .brief import assemble_assessment, assemble_brief
from .context import AnalysisContext
from .grounding import ground_refs
from .providers.base import LLMError
from .stages.base import BriefWriter, Extractor, RubricAnalyzer, Verifier
from .stages.heuristic.stages import (
    HeuristicBriefWriter,
    HeuristicExtractor,
    HeuristicRubricAnalyzer,
    HeuristicVerifier,
)

log = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0"
EVIDENCE_REQUIRED = {"unsupported_claim", "feasibility_gap", "inconsistency"}


class AnalysisFailed(Exception):
    pass


@dataclass
class AnalysisResult:
    extraction: ExtractionOutput
    rubric: RubricAnalysisOutput
    verification: VerificationOutput
    brief: JudgeBrief
    assessment: AIAssessment


class AnalysisPipeline:
    def __init__(
        self,
        *,
        extractor: Extractor,
        rubric_analyzer: RubricAnalyzer,
        verifier: Verifier,
        brief_writer: BriefWriter,
        engine: str,
        model: str | None,
        note: str,
    ):
        self.extractor = extractor
        self.rubric_analyzer = rubric_analyzer
        self.verifier = verifier
        self.brief_writer = brief_writer
        self.engine = engine
        self.model = model
        self.note = note

    def run(self, ctx: AnalysisContext) -> AnalysisResult:
        try:
            extraction = self.extractor.extract(ctx)
            for topic in extraction.topics:
                topic.evidence = ground_refs(topic.evidence, ctx)
            extraction.topics = [t for t in extraction.topics if t.evidence]
            for claim in extraction.claims:
                claim.evidence = ground_refs(claim.evidence, ctx)
            extraction.claims = [c for c in extraction.claims if c.evidence]

            rubric = self.rubric_analyzer.analyze(ctx, extraction)
            for c in rubric.criteria:
                c.evidence = ground_refs(c.evidence, ctx)
                if c.assessed and not c.evidence:
                    # A score without a traceable source is not shown.
                    c.assessed, c.score = False, None
                    c.not_assessed_reason = "No verifiable evidence could be linked to this assessment."
                if not c.assessed:
                    c.score = None

            verification = self.verifier.verify(ctx, extraction, rubric)
            kept = []
            for item in verification.items:
                item.evidence = ground_refs(item.evidence, ctx)
                if item.type in EVIDENCE_REQUIRED and not item.evidence:
                    log.info("Dropping verify item without linkable evidence: %s", item.title)
                    continue
                if item.type == "potential_similarity" and not item.label:
                    item.label = "Potential similarity — human verification required."
                kept.append(item)
            verification.items = kept

            writer = self.brief_writer.write(ctx, extraction, rubric, verification)
            for s in writer.strengths:
                s.evidence = ground_refs(s.evidence, ctx)
            writer.strengths = [s for s in writer.strengths if s.evidence]
        except LLMError as exc:
            raise AnalysisFailed(str(exc)) from exc
        except Exception as exc:  # validation errors, provider bugs, etc.
            log.exception("AI analysis failed")
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        provenance = BriefProvenance(
            engine=self.engine,
            model=self.model,
            pipeline_version=PIPELINE_VERSION,
            stages=[
                self.extractor.name,
                self.rubric_analyzer.name,
                self.verifier.name,
                self.brief_writer.name,
            ],
            note=self.note,
        )
        brief = assemble_brief(ctx, extraction, rubric, verification, writer, provenance)
        assessment = assemble_assessment(ctx, rubric, engine=self.engine, model=self.model)
        return AnalysisResult(extraction, rubric, verification, brief, assessment)


def build_pipeline(settings: Settings) -> AnalysisPipeline:
    if settings.ai_engine == "anthropic":
        from .providers.anthropic_provider import AnthropicProvider
        from .stages.llm.stages import LLMBriefWriter, LLMExtractor, LLMRubricAnalyzer, LLMVerifier

        provider = AnthropicProvider(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
            fallbacks=settings.anthropic_fallbacks,
        )
        return AnalysisPipeline(
            extractor=LLMExtractor(provider),
            rubric_analyzer=LLMRubricAnalyzer(provider),
            verifier=LLMVerifier(provider),
            brief_writer=LLMBriefWriter(provider),
            engine="anthropic",
            model=settings.anthropic_model,
            note="Generated by a large language model from the extracted evidence pack. "
            "Findings are grounded to slides; excerpts that could not be matched are marked unverified.",
        )
    return AnalysisPipeline(
        extractor=HeuristicExtractor(),
        rubric_analyzer=HeuristicRubricAnalyzer(),
        verifier=HeuristicVerifier(),
        brief_writer=HeuristicBriefWriter(),
        engine="rule-based",
        model=None,
        note="Offline rule-based analyzer: locates evidence and flags claims using transparent text rules. "
        "It does not interpret meaning the way a language model would.",
    )
