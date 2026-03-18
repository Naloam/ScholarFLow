from __future__ import annotations

import services.llm.client as llm_client
from config.settings import settings
from services.telemetry.usage import estimate_cost_usd


class _FakeUsage:
    def __init__(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        prompt_cache_hit_tokens: int,
        prompt_cache_miss_tokens: int,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.prompt_cache_hit_tokens = prompt_cache_hit_tokens
        self.prompt_cache_miss_tokens = prompt_cache_miss_tokens

    def get(self, key: str, default=None):
        return getattr(self, key, default)


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content

    def get(self, key: str, default=None):
        return getattr(self, key, default)


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)

    def get(self, key: str, default=None):
        return getattr(self, key, default)


class _FakeResponse:
    def __init__(
        self,
        *,
        content: str,
        prompt_tokens: int,
        completion_tokens: int,
        prompt_cache_hit_tokens: int,
        prompt_cache_miss_tokens: int,
    ) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            prompt_cache_miss_tokens=prompt_cache_miss_tokens,
        )

    def get(self, key: str, default=None):
        return getattr(self, key, default)


def test_chat_records_usage_for_litellm_style_responses(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    monkeypatch.delenv("SCHOLARFLOW_OFFLINE_LLM", raising=False)
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_api_base", "https://api.deepseek.com")
    monkeypatch.setattr(
        llm_client,
        "litellm_completion",
        lambda **_: _FakeResponse(
            content="Synthetic response",
            prompt_tokens=16,
            completion_tokens=7,
            prompt_cache_hit_tokens=3,
            prompt_cache_miss_tokens=13,
        ),
    )
    monkeypatch.setattr(llm_client, "record_usage_event", lambda **kwargs: recorded.update(kwargs))

    response = llm_client.chat(
        [{"role": "user", "content": "hello"}],
        model="deepseek/deepseek-chat",
    )

    assert response.get("choices")[0].get("message").get("content") == "Synthetic response"
    assert recorded["model"] == "deepseek/deepseek-chat"
    assert recorded["prompt_tokens"] == 16
    assert recorded["completion_tokens"] == 7
    assert recorded["prompt_cache_hit_tokens"] == 3
    assert recorded["prompt_cache_miss_tokens"] == 13


def test_estimate_cost_usd_handles_deepseek_cache_pricing() -> None:
    cost = estimate_cost_usd(
        "chat",
        "deepseek/deepseek-chat",
        prompt_tokens=1000,
        completion_tokens=1000,
        prompt_cache_hit_tokens=250,
        prompt_cache_miss_tokens=750,
    )

    assert cost == 0.000637
