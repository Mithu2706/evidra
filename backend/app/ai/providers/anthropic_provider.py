"""Claude via the official Anthropic SDK, using structured outputs.

The API key is read from the environment on the server and is never sent to
the frontend.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from .base import LLMError, LLMProvider

log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, *, api_key: str, model: str, effort: str = "high", fallbacks: bool = True):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self.model = model
        self.effort = effort
        self.fallbacks = fallbacks
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=600)

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_tokens: int = 32000
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        }
        if self.fallbacks:
            # If a safety classifier declines, let the API re-run the request on
            # its recommended fallback model instead of failing outright.
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"

        try:
            with self.client.beta.messages.stream(**kwargs) as stream:
                message = stream.get_final_message()
        except anthropic.RateLimitError as exc:
            raise LLMError("Model provider rate limit reached") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Model provider returned HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the model provider") from exc

        if message.stop_reason == "refusal":
            raise LLMError("The model declined to analyze this submission")
        if message.stop_reason == "max_tokens":
            raise LLMError("Model output was truncated")

        text = next((b.text for b in message.content if b.type == "text"), None)
        if not text:
            raise LLMError("Model returned no content")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("Model returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise LLMError("Model returned a non-object JSON value")
        return data
