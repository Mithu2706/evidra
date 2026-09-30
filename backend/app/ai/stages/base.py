"""The four AI pipeline stages.

Each stage is an interface with (at least) two implementations:
a deterministic rule-based one (offline, no model calls) and an LLM-backed
one that works with any `LLMProvider`. They can be mixed freely.

    Extractor        — understands the submission and organizes evidence
    RubricAnalyzer   — evaluates evidence against organizer-defined criteria
    Verifier         — challenges unsupported claims → "Verify These"
    BriefGenerator   — turns findings into the judge-facing brief
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...schemas.ai import (
    BriefWriterOutput,
    ExtractionOutput,
    RubricAnalysisOutput,
    VerificationOutput,
)
from ..context import AnalysisContext


class Extractor(ABC):
    name: str

    @abstractmethod
    def extract(self, ctx: AnalysisContext) -> ExtractionOutput: ...


class RubricAnalyzer(ABC):
    name: str

    @abstractmethod
    def analyze(self, ctx: AnalysisContext, extraction: ExtractionOutput) -> RubricAnalysisOutput: ...


class Verifier(ABC):
    name: str

    @abstractmethod
    def verify(
        self, ctx: AnalysisContext, extraction: ExtractionOutput, rubric: RubricAnalysisOutput
    ) -> VerificationOutput: ...


class BriefWriter(ABC):
    """Writes the narrative parts of the brief. Structural assembly (evidence
    map, integrity, not-assessed, rubric coverage) is done by deterministic
    code in `ai.brief` so those sections can never be invented by a model."""

    name: str

    @abstractmethod
    def write(
        self,
        ctx: AnalysisContext,
        extraction: ExtractionOutput,
        rubric: RubricAnalysisOutput,
        verification: VerificationOutput,
    ) -> BriefWriterOutput: ...
