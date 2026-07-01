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
from typing import Any, Iterator, Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolSpec:
    """A tool/function the model may call (OpenAI-compatible JSON schema)."""

    name: str
    description: str
    parameters: dict  # JSON schema for the arguments object


@dataclass
class ToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict


@dataclass
class Message:
    role: Role
    content: str = ""
    # Present on assistant turns that request tool calls:
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Present on role="tool" result turns:
    tool_call_id: str | None = None


@dataclass
class ChatResult:
    """Non-streaming chat response (may carry tool calls instead of content)."""

    content: str
    model: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Unified interface every LLM backend must implement."""

    name: str

    def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: Any = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Return a full chat completion, optionally with tool calls."""
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
