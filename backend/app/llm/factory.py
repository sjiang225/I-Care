"""Build the configured LLMProvider. The ONLY place that knows concrete classes."""
from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import LLMProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    provider = s.llm_provider.lower()

    if provider == "openai":
        return OpenAIProvider(
            api_key=s.openai_api_key,
            base_url=s.openai_base_url,
            chat_model=s.openai_chat_model,
            embed_model=s.openai_embed_model,
        )
    if provider == "mock":
        return MockProvider()

    raise ValueError(f"Unknown LLM_PROVIDER: {s.llm_provider!r}")
