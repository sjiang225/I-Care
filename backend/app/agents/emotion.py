"""Emotion-Support Agent: empathetic dialogue + stress monitoring.

Flow:
  1. Retrieve self-care / coping material for grounded, practical suggestions.
  2. Assess + log the caregiver's well-being via the log_wellbeing TOOL CALL
     (this is the proposal's "track stress over time" feature).
  3. Stream a warm, validating response with light, citable coping guidance.
"""
from __future__ import annotations

from typing import Iterator

from ..kb.retrieve import retrieve
from ..llm.base import Message
from ..llm.factory import get_llm
from ..tools import wellbeing as _wb  # noqa: F401  (registers the tool)
from ..tools.base import registry
from ..tools.wellbeing import LOG_WELLBEING_SPEC
from .base import AgentContext, AgentEvent
from .education import build_context_and_sources

EMOTION_SYSTEM = """You are I-Care, a warm, compassionate companion for dementia \
caregivers. The caregiver is sharing how they feel.

Rules:
- Lead with genuine empathy: validate their feelings and reassure them they are \
not alone. Caregiver guilt, grief, anger, and exhaustion are normal.
- Then offer one or two gentle, practical self-care suggestions. If they are \
drawn from the reference material, cite them inline like [1].
- Be brief, warm, and human. Plain language, short paragraphs.
- Gently mention that support is available: Care2Caregivers helpline \
1-800-424-2494.
- You are not a therapist. If they mention thoughts of self-harm or crisis, \
urge them to call or text 988 immediately.

Reference material (self-care):
{context}"""


class EmotionSupportAgent:
    name = "emotion"

    def __init__(self, history_turns: int = 6) -> None:
        self._history_turns = history_turns

    def _assess_and_log(self, ctx: AgentContext) -> dict | None:
        """One forced tool call -> structured well-being signal, logged to DB."""
        try:
            result = get_llm().chat(
                [
                    Message(
                        role="system",
                        content=(
                            "Assess the caregiver's emotional state from the "
                            "conversation and record it by calling log_wellbeing."
                        ),
                    ),
                    *ctx.recent(self._history_turns),
                ],
                tools=[LOG_WELLBEING_SPEC],
                tool_choice={"type": "function", "function": {"name": "log_wellbeing"}},
                temperature=0,
            )
            if result.tool_calls:
                return registry.dispatch(result.tool_calls[0], ctx.session_id)
        except Exception:
            # Logging is best-effort; never block the supportive reply.
            return None
        return None

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        hits = retrieve(ctx.last_user_text(), k=3)
        context, sources = build_context_and_sources(hits)
        yield ("sources", sources)

        logged = self._assess_and_log(ctx)
        if logged:
            yield ("signal", {"wellbeing": logged})

        system = Message(role="system", content=EMOTION_SYSTEM.format(context=context))
        prompt = [system, *ctx.recent(self._history_turns)]
        for delta in get_llm().stream_chat(prompt, temperature=0.6):
            yield ("delta", delta)
