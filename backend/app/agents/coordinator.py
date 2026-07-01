"""Coordinator Agent: safety pre-check, intent routing, and orchestration.

For each turn:
  1. Safety guardrail -> if it fires, surface an urgent notice first.
  2. Route the message (education vs emotional support) via a structured tool
     call.
  3. Delegate to the chosen specialist agent, passing emotional context so an
     educational answer can still open with empathy.
"""
from __future__ import annotations

from typing import Iterator

from ..llm.base import Message, ToolSpec
from ..llm.factory import get_llm
from .base import Agent, AgentContext, AgentEvent
from .education import EducationAgent
from .emotion import EmotionSupportAgent
from .safety import check_safety

ROUTE_SPEC = ToolSpec(
    name="route",
    description="Classify the caregiver's latest message to route the response.",
    parameters={
        "type": "object",
        "properties": {
            "needs_education": {
                "type": "boolean",
                "description": "True if they ask for factual or how-to caregiving info.",
            },
            "needs_emotion": {
                "type": "boolean",
                "description": "True if they express stress, distress, or emotional burden.",
            },
            "primary": {
                "type": "string",
                "enum": ["education", "emotion"],
                "description": "Which response should lead.",
            },
        },
        "required": ["primary", "needs_education", "needs_emotion"],
    },
)

ROUTE_SYSTEM = (
    "You route messages from dementia caregivers in an support app. "
    "Decide whether the latest message primarily needs practical/educational "
    "guidance or emotional support, and whether emotional distress is present. "
    "Record your decision by calling the route function."
)


class Coordinator:
    name = "coordinator"

    def __init__(self) -> None:
        self._education = EducationAgent()
        self._emotion = EmotionSupportAgent()

    def _route(self, ctx: AgentContext) -> dict:
        try:
            res = get_llm().chat(
                [Message(role="system", content=ROUTE_SYSTEM), *ctx.recent(4)],
                tools=[ROUTE_SPEC],
                tool_choice={"type": "function", "function": {"name": "route"}},
                temperature=0,
            )
            if res.tool_calls:
                return res.tool_calls[0].arguments
        except Exception:
            pass
        # Safe default: treat as an educational question.
        return {"primary": "education", "needs_education": True, "needs_emotion": False}

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        safety = check_safety(ctx.last_user_text())
        if safety.triggered:
            yield ("signal", {"safety": safety.category})
            yield ("delta", safety.message or "")

        route = self._route(ctx)
        ctx.flags["needs_emotion"] = bool(route.get("needs_emotion"))

        agent: Agent = (
            self._emotion if route.get("primary") == "emotion" else self._education
        )
        yield from agent.stream(ctx)
