"""Mock LLMProvider for local development without an API key / network.

Returns canned, deterministic responses so the whole app (frontend, streaming,
agents) can be built and demoed before real keys / compliant hosting exist.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterator

from .base import ChatResult, Message, ToolCall, ToolSpec


def _mock_args(spec: ToolSpec) -> dict:
    """Fabricate plausible default arguments from a tool's JSON schema."""
    args: dict = {}
    props = spec.parameters.get("properties", {})
    for name, schema in props.items():
        t = schema.get("type")
        if "enum" in schema:
            args[name] = schema["enum"][0]
        elif t == "integer" or t == "number":
            args[name] = schema.get("minimum", 0)
        elif t == "array":
            args[name] = []
        elif t == "boolean":
            args[name] = False
        else:
            args[name] = "mock"
    return args

_DISCLAIMER = (
    "(Mock mode) I-Care is an educational support tool, not a medical "
    "diagnosis. In an emergency, call 911 or your doctor."
)


def _reply_for(messages: list[Message]) -> str:
    last_user = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )
    return (
        f"Thanks for sharing. You said: “{last_user.strip()}”. "
        "Here is some general guidance for dementia caregivers. "
        "Once the Care2Caregivers knowledge base is connected, this answer "
        "will be evidence-based and cite its sources.\n\n" + _DISCLAIMER
    )


class MockProvider:
    name = "mock"

    def __init__(self, chat_model: str = "mock-1", embed_dim: int = 1536) -> None:
        self._chat_model = chat_model
        self._embed_dim = embed_dim

    def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: Any = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        # If a specific tool is forced, return a canned call so tool-using
        # agent paths are exercisable without an API key.
        if tools and isinstance(tool_choice, dict):
            forced = tool_choice.get("function", {}).get("name")
            spec = next((t for t in tools if t.name == forced), None)
            if spec is not None:
                return ChatResult(
                    content="",
                    model=self._chat_model,
                    tool_calls=[
                        ToolCall(
                            id="mock-call-1",
                            name=spec.name,
                            arguments=_mock_args(spec),
                        )
                    ],
                )
        return ChatResult(content=_reply_for(messages), model=self._chat_model)

    def stream_chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        # Emit word-by-word so the frontend streaming path is exercised.
        for word in _reply_for(messages).split(" "):
            yield word + " "

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Deterministic pseudo-embeddings derived from text hash.
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            seed = list(digest) * (self._embed_dim // len(digest) + 1)
            vectors.append([(b / 255.0) for b in seed[: self._embed_dim]])
        return vectors
