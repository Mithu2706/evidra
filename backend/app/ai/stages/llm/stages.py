"""LLM-backed implementations of the four AI stages (provider-agnostic)."""

from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ....schemas.ai import (
    BriefWriterOutput,
    ExtractionOutput,
    RubricAnalysisOutput,
    VerificationOutput,
)
from ...context import AnalysisContext
from ...providers.base import LLMError, LLMProvider, llm_json_schema
from ..base import BriefWriter, Extractor, RubricAnalyzer, Verifier
from . import prompts

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def _call(provider: LLMProvider, model_cls: type[T], prompt: str, stage: str) -> T:
    """Call the model and validate against the schema; one corrective retry."""
    schema = llm_json_schema(model_cls)
    system = prompts.SYSTEM_BASE
    last_error: Exception | None = None
    for attempt in range(2):
        data = provider.generate_json(system=system, prompt=prompt, schema=schema)
        try:
            return model_cls.model_validate(data)
        except ValidationError as exc:
            last_error = exc
            log.warning("%s output failed validation (attempt %d): %s", stage, attempt + 1, exc)
            prompt = (
                f"{prompt}\n\nYour previous answer did not match the required schema:\n"
                f"{exc.errors()[:5]}\nReturn a corrected JSON object."
            )
    raise LLMError(f"{stage}: model output failed schema validation") from last_error


class LLMExtractor(Extractor):
    name = "llm-extractor"

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def extract(self, ctx: AnalysisContext) -> ExtractionOutput:
        return _call(self.provider, ExtractionOutput, prompts.extractor_prompt(ctx), "extractor")


class LLMRubricAnalyzer(RubricAnalyzer):
    name = "llm-rubric-analyzer"

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def analyze(self, ctx: AnalysisContext, extraction: ExtractionOutput) -> RubricAnalysisOutput:
        result = _call(
            self.provider,
            RubricAnalysisOutput,
            prompts.rubric_prompt(ctx, extraction.model_dump_json(indent=1)),
            "rubric_analyzer",
        )
        known = {c.id for c in ctx.criteria}
        result.criteria = [c for c in result.criteria if c.criterion_id in known]
        missing = known - {c.criterion_id for c in result.criteria}
        if missing:
            raise LLMError(f"rubric_analyzer: no assessment returned for criteria {sorted(missing)}")
        return result


class LLMVerifier(Verifier):
    name = "llm-verifier"

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def verify(self, ctx, extraction, rubric) -> VerificationOutput:
        return _call(
            self.provider,
            VerificationOutput,
            prompts.verifier_prompt(
                ctx, extraction.model_dump_json(indent=1), rubric.model_dump_json(indent=1)
            ),
            "verifier",
        )


class LLMBriefWriter(BriefWriter):
    name = "llm-brief-writer"

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def write(self, ctx, extraction, rubric, verification) -> BriefWriterOutput:
        return _call(
            self.provider,
            BriefWriterOutput,
            prompts.writer_prompt(
                ctx, extraction.model_dump_json(indent=1), verification.model_dump_json(indent=1)
            ),
            "brief_writer",
        )
