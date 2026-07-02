"""Coordinator Agent: safety pre-check, intent routing, and multi-agent composition.

For each turn:
  1. Safety guardrail -> if it fires, surface an urgent notice first.
  2. Route the message (needs_education / needs_emotion) via a structured tool call.
  3. Build an ordered Plan of specialist agents and execute them sequentially,
     streaming throughout. When both are needed: Emotion (empathy + log) first,
     then a connector, then Education (grounded answer with citations).

See docs/agent-orchestration.md for the design + rationale.
"""
from __future__ import annotations

from typing import Iterator

from ..db import get_db
from ..llm.base import Message, ToolSpec
from ..llm.factory import get_llm
from ..tools import resources as resources_tool
from .base import AgentContext, AgentEvent
from .education import EducationAgent
from .emotion import EmotionSupportAgent
from .peer import PeerSupportAgent
from .registry import AgentRegistry
from .safety import check_safety
from .state import assess_caregiver_state

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
                "description": "True if they express acute stress, distress, or emotional burden.",
            },
            "needs_peer": {
                "type": "boolean",
                "description": "True if they feel alone/isolated, misunderstood, doubt whether their experience is normal, or want to feel connected to others who understand.",
            },
            "needs_resources": {
                "type": "boolean",
                "description": "True if they ask about finding care, facilities, services, or local/NJ help.",
            },
            "county": {
                "type": "string",
                "description": "NJ county name (e.g. 'Bergen') if a location is mentioned; else omit.",
            },
            "primary": {
                "type": "string",
                "enum": ["education", "emotion"],
                "description": "Which need is dominant (for emphasis).",
            },
        },
        "required": ["primary", "needs_education", "needs_emotion"],
    },
)

ROUTE_SYSTEM = (
    "You route messages from dementia caregivers in a support app. Decide whether "
    "the latest message needs practical/educational guidance (needs_education), "
    "acute emotional support (needs_emotion), peer connection/normalization when "
    "they feel alone or wonder if their experience is normal (needs_peer), and/or "
    "local resources (needs_resources — finding care/facilities/services; extract a "
    "NJ county if named). Record your decision by calling the route function."
)

# Shown between the Emotion and Education segments when both run.
CONNECTOR = "\n\nHere are some practical things that may help:\n\n"


class Coordinator:
    name = "coordinator"

    def __init__(self) -> None:
        self._registry = AgentRegistry()
        self._registry.register(EducationAgent())
        self._registry.register(EmotionSupportAgent())
        self._registry.register(PeerSupportAgent())

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

    def _build_plan(self, route: dict) -> list[str]:
        """Ordered list of agent names. At most one supportive voice (acute
        emotion takes priority over peer), then education as the fallback so every
        turn produces an answer."""
        steps: list[str] = []
        if route.get("needs_emotion"):
            steps.append("emotion")
        elif route.get("needs_peer"):
            steps.append("peer")
        if route.get("needs_education") or not steps:
            steps.append("education")
        return steps

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        safety = check_safety(ctx.last_user_text())
        if safety.triggered:
            yield ("signal", {"safety": safety.category})
            yield ("delta", safety.message or "")

        route = self._route(ctx)

        # Deterministically fetch NJ resources when the router flags a need, and
        # hand them to the Education agent via flags (no extra LLM call).
        if route.get("needs_resources"):
            ctx.flags["resources"] = resources_tool.get_local_resources(
                county=route.get("county")
            )

        # Well-being feedback loop: if the stored trend shows high/rising stress,
        # adopt a warmer posture and surface self-care support (no extra LLM call).
        state = assess_caregiver_state(get_db().wellbeing_summary(ctx.session_id))
        if state.high_stress:
            ctx.flags["high_stress"] = True
            ctx.flags["caregiver_state"] = state.note
            ctx.flags["extra_video_category"] = "caregiver_selfcare"
            ctx.flags.setdefault("resources", resources_tool.get_local_resources())

        plan = self._build_plan(route)
        yield ("signal", {"plan": plan})

        for i, name in enumerate(plan):
            if i > 0:
                yield ("delta", CONNECTOR)
            # Tell later agents whether a supportive voice already spoke this turn.
            ctx.flags["empathy_done"] = any(
                a in plan[:i] for a in ("emotion", "peer")
            )
            ctx.flags["needs_emotion"] = bool(route.get("needs_emotion"))
            yield from self._registry.get(name).stream(ctx)
