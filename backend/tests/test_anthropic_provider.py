"""AnthropicProvider integration contract, with the SDK client stubbed (no network)."""

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.ai.pipeline import AnalysisFailed, build_pipeline
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import LLMError, llm_json_schema
from app.config import Settings
from app.schemas.ai import ExtractionOutput

from test_ai_pipeline import make_ctx

FAKE_KEY = "sk-ant-test-not-a-real-key"


class _Stream:
    def __init__(self, message=None, error=None):
        self.message, self.error = message, error

    def __enter__(self):
        if self.error:
            raise self.error
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


def stub(provider: AnthropicProvider, *, text=None, stop_reason="end_turn", error=None, calls=None):
    content = [] if text is None else [SimpleNamespace(type="text", text=text)]
    message = SimpleNamespace(stop_reason=stop_reason, content=content)

    def stream(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return _Stream(message, error)

    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    return provider


def provider(**kw) -> AnthropicProvider:
    return AnthropicProvider(api_key=FAKE_KEY, model="claude-opus-5-5", **kw)


def test_missing_key_fails_cleanly():
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY is not set"):
        AnthropicProvider(api_key="", model="claude-opus-5-5")


def test_request_uses_structured_output_and_no_secret():
    calls: list[dict] = []
    p = stub(provider(), text='{"ok": true}', calls=calls)
    schema = llm_json_schema(ExtractionOutput)
    assert p.generate_json(system="s", prompt="p", schema=schema) == {"ok": True}
    kwargs = calls[0]
    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["output_config"]["format"] == {"type": "json_schema", "schema": schema}
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["fallbacks"] == "default" and kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert FAKE_KEY not in repr(kwargs)


def test_fallbacks_can_be_disabled():
    calls: list[dict] = []
    stub(provider(fallbacks=False), text="{}", calls=calls).generate_json(system="s", prompt="p", schema={})
    assert "fallbacks" not in calls[0] and "betas" not in calls[0]


@pytest.mark.parametrize(
    "text, stop_reason, message",
    [
        ("not json", "end_turn", "invalid JSON"),
        ("[1, 2]", "end_turn", "non-object"),
        (None, "end_turn", "no content"),
        ('{"partial": ', "max_tokens", "truncated"),
        ("", "refusal", "declined"),
    ],
)
def test_bad_responses_raise_llm_error(text, stop_reason, message):
    with pytest.raises(LLMError, match=message):
        stub(provider(), text=text, stop_reason=stop_reason).generate_json(system="s", prompt="p", schema={})


def test_transport_errors_are_mapped_without_secrets():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.APIConnectionError(request=request)
    with pytest.raises(LLMError, match="Could not reach") as info:
        stub(provider(), error=err).generate_json(system="s", prompt="p", schema={})
    assert FAKE_KEY not in str(info.value)


def test_malformed_model_output_fails_whole_analysis(monkeypatch):
    """A schema-violating response must mark the analysis failed, not produce a partial brief."""
    settings = Settings(EVIDRA_AI_ENGINE="anthropic", ANTHROPIC_API_KEY=FAKE_KEY)
    pipeline = build_pipeline(settings)
    stub(pipeline.extractor.provider, text='{"overview": 42}')
    with pytest.raises(AnalysisFailed, match="schema validation"):
        pipeline.run(make_ctx())


ANTHROPIC_ENV = {
    "EVIDRA_AI_ENGINE": "anthropic",
    "ANTHROPIC_API_KEY": FAKE_KEY,
    "EVIDRA_ANTHROPIC_MODEL": "claude-sonnet-5-5",
    "EVIDRA_ANTHROPIC_EFFORT": "medium",
    "EVIDRA_ANTHROPIC_FALLBACKS": "false",
}


def test_effort_env_var_reaches_request(monkeypatch):
    monkeypatch.setenv("EVIDRA_AI_ENGINE", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    monkeypatch.setenv("EVIDRA_ANTHROPIC_EFFORT", "medium")
    calls: list[dict] = []
    stub(build_pipeline(Settings()).extractor.provider, text="{}", calls=calls).generate_json(
        system="s", prompt="p", schema={}
    )
    assert calls[0]["output_config"]["effort"] == "medium"


def test_anthropic_env_vars_flow_into_provider_and_pipeline(monkeypatch):
    for name, value in ANTHROPIC_ENV.items():
        monkeypatch.setenv(name, value)
    pipeline = build_pipeline(Settings())
    prov = pipeline.extractor.provider

    assert isinstance(prov, AnthropicProvider)
    assert pipeline.engine == "anthropic" and pipeline.model == "claude-sonnet-5-5"
    assert all(stage.provider is prov for stage in (pipeline.rubric_analyzer, pipeline.verifier, pipeline.brief_writer))
    assert prov.client.api_key == FAKE_KEY
    assert (prov.model, prov.effort, prov.fallbacks) == ("claude-sonnet-5-5", "medium", False)

    calls: list[dict] = []
    stub(prov, text="{}", calls=calls).generate_json(system="s", prompt="p", schema={})
    request = calls[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["output_config"]["effort"] == "medium"
    assert "fallbacks" not in request and "betas" not in request
    assert FAKE_KEY not in repr(request)
