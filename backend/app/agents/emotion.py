"""Emotion-Support Agent: empathetic dialogue + stress monitoring.

Role: AFFECTIVE support (warmth), not factual delivery. To keep composition with
the Education agent clean, this agent:
  * does NOT emit `sources` and does NOT use [n] citations;
  * MAY use self-care material silently to make suggestions concrete;
  * assesses + logs the caregiver's well-being via the log_wellbeing TOOL CALL.

(Education is the sole source/citation emitter -- see docs/agent-orchestration.md.)
"""
from __future__ import annotations

from typing import Iterator

from ..kb.retrieve import retrieve
from ..llm.base import Message
from ..llm.factory import get_llm
from .base import AgentContext, AgentEvent
from .wellbeing_logging import assess_and_log_wellbeing

EMOTION_SYSTEM = """You are I-Care, a warm, compassionate companion for dementia \
caregivers. The caregiver is sharing how they feel.

Rules:
- Lead with genuine empathy: validate their feelings and reassure them they are \
not alone. Caregiver guilt, grief, anger, and exhaustion are normal.
- Then offer one or two gentle, practical self-care suggestions. You may draw on \
the background notes below, but weave them in naturally -- do NOT use citation \
markers like [1].
- Be brief, warm, and human. Plain language, short paragraphs.
- Gently mention that support is available: Care2Caregivers helpline \
1-800-424-2494.
- You are not a therapist. If they mention thoughts of self-harm or crisis, \
urge them to call or text 988 immediately.

Background notes (self-care, for your reference only):
{context}"""


def _plain_context(hits) -> str:
    """Concatenate retrieved text WITHOUT citation numbers (silent grounding)."""
    return "\n\n".join(h.text for h in hits)


class EmotionSupportAgent:
    name = "emotion"

    def __init__(self, history_turns: int = 6) -> None:
        self._history_turns = history_turns

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        logged = assess_and_log_wellbeing(ctx, self._history_turns)
        if logged:
            yield ("signal", {"wellbeing": logged})

        hits = retrieve(ctx.last_user_text(), k=3)
        system_content = EMOTION_SYSTEM.format(context=_plain_context(hits))
        if ctx.flags.get("caregiver_state"):
            system_content += "\n\n" + ctx.flags["caregiver_state"]
        system = Message(role="system", content=system_content)
        prompt = [system, *ctx.recent(self._history_turns)]
        for delta in get_llm().stream_chat(prompt, temperature=0.6):
            yield ("delta", delta)
