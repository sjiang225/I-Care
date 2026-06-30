"""LLM provider abstraction.

Business code (agents, RAG, API endpoints) must depend ONLY on this module,
never on a vendor SDK directly. This is what makes swapping GPT -> a future
self-hosted small model a config change, not a code change.

To plug in a self-hosted model later:
  * If it exposes an OpenAI-compatible API (vLLM / Ollama / TGI),
    reuse OpenAIProvider and just change OPENAI_BASE_URL + model name.
  * Otherwise, write a new class implementing LLMProvider and register it
    in factory.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str


@dataclass
class ChatResult:
    """Non-streaming chat response."""

    content: str
    model: str
    raw: dict = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Unified interface every LLM backend must implement."""

    name: str

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Return a full chat completion."""
        ...

    def stream_chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Yield response text incrementally (token/delta chunks)."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text (used by RAG)."""
        ...
