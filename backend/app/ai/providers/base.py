"""Vendor-neutral LLM provider interface.

The pipeline only needs "give me JSON matching this schema". Adding another
vendor means implementing `generate_json` in a new class and registering it in
`ai.pipeline.build_pipeline`.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMError(Exception):
    """Any failure to obtain a valid structured response from a model."""


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_tokens: int = 16000
    ) -> dict[str, Any]:
        """Return a JSON object that conforms to `schema` (raise LLMError otherwise)."""


# Fields populated by our own grounding step; the model must not fill them.
_SERVER_ONLY_FIELDS = {"page_number", "verified", "via"}
_UNSUPPORTED_KEYWORDS = {
    "title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "pattern", "format", "minItems", "maxItems",
}


def llm_json_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Pydantic model → strict JSON schema suitable for constrained decoding.

    Every object gets `additionalProperties: false` and all properties become
    required (optional ones are nullable), which strict structured-output
    modes expect. Server-only fields are removed.
    """
    schema = copy.deepcopy(model_cls.model_json_schema())

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            for key in list(node):
                if key in _UNSUPPORTED_KEYWORDS and not isinstance(node.get(key), dict | list):
                    node.pop(key)
            if node.get("type") == "object" and "properties" in node:
                for f in _SERVER_ONLY_FIELDS & set(node["properties"]):
                    node["properties"].pop(f)
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        return node

    return walk(schema)
