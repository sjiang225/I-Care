"""Agent framework primitives.

A light, provider-agnostic foundation for the multi-agent system:
  * AgentContext  -- per-request state (conversation + session) shared by agents.
  * AgentEvent    -- the streaming protocol agents emit (sources / delta / signal).
  * Agent         -- the interface every agent implements.

Kept intentionally minimal so it runs on our own LLMProvider abstraction and we
can swap GPT -> a self-hosted model without touching agent code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal, Protocol

from ..llm.base import Message

# What an agent streams back. Consumed by the API layer and turned into SSE.
#   ("sources", list[Source])  -- citations for the answer
#   ("delta",   str)           -- a chunk of answer text
#   ("signal",  dict)          -- a side-channel event (e.g. wellbeing logged)
EventKind = Literal["sources", "delta", "signal"]
AgentEvent = tuple[EventKind, object]


@dataclass
class AgentContext:
    """Everything an agent needs about the current request."""

    messages: list[Message]
    session_id: str = "default"
    # Coordinator fills this so downstream agents can adapt tone, e.g. when an
    # educational question also carries emotional distress.
    flags: dict = field(default_factory=dict)

    def last_user_text(self) -> str:
        for m in reversed(self.messages):
            if m.role == "user":
                return m.content
        return ""

    def recent(self, turns: int) -> list[Message]:
        non_system = [m for m in self.messages if m.role != "system"]
        return non_system[-turns:]


class Agent(Protocol):
    name: str

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        """Handle the request, yielding AgentEvents."""
        ...
