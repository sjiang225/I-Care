"""OpenAI-backed LLMProvider.

Also works unchanged against any OpenAI-compatible server (vLLM / Ollama / TGI)
by pointing base_url at it -- this is the migration path to a self-hosted
small model.
"""
from __future__ import annotations

from typing import Iterator

from openai import OpenAI

from .base import ChatResult, Message


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_model: str,
        embed_model: str,
    ) -> None:
        # api_key may be a placeholder for local servers that don't check it.
        self._client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)
        self._chat_model = chat_model
        self._embed_model = embed_model

    def _to_openai(self, messages: list[Message]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        resp = self._client.chat.completions.create(
            model=self._chat_model,
            messages=self._to_openai(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return ChatResult(
            content=resp.choices[0].message.content or "",
            model=resp.model,
            raw=resp.model_dump(),
        )

    def stream_chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self._chat_model,
            messages=self._to_openai(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._embed_model, input=texts)
        return [item.embedding for item in resp.data]
