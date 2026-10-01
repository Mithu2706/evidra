"""Export the shared JSON Schemas (Evidence Pack and AI outputs) to /shared/schemas.

    python -m scripts.export_schemas   (run from backend/)
"""

from __future__ import annotations

import json
from pathlib import Path

from app.ai.providers.base import llm_json_schema
from app.schemas.ai import (
    AIAssessment,
    BriefWriterOutput,
    ExtractionOutput,
    JudgeBrief,
    RubricAnalysisOutput,
    VerificationOutput,
)
from app.schemas.evidence import EvidencePack

OUT = Path(__file__).resolve().parents[2] / "shared" / "schemas"

MODELS = {
    "evidence_pack": EvidencePack,
    "judge_brief": JudgeBrief,
    "ai_assessment": AIAssessment,
}
# Schemas the LLM stages are constrained to (strict form, server-only fields removed).
LLM_MODELS = {
    "llm_extraction": ExtractionOutput,
    "llm_rubric_analysis": RubricAnalysisOutput,
    "llm_verification": VerificationOutput,
    "llm_brief_writer": BriefWriterOutput,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        (OUT / f"{name}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
    for name, model in LLM_MODELS.items():
        (OUT / f"{name}.schema.json").write_text(json.dumps(llm_json_schema(model), indent=2) + "\n")
    print(f"Wrote {len(MODELS) + len(LLM_MODELS)} schemas to {OUT}")


if __name__ == "__main__":
    main()
