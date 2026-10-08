"""Emotion-Support Agent: empathetic dialogue without automatic mood scoring.

Role: AFFECTIVE support (warmth), not factual delivery. To keep composition with
the Education agent clean, this agent:
  * does NOT emit `sources` and does NOT use [n] citations;
  * MAY use self-care material silently to make suggestions concrete;
  * does not infer, record, or consult stored well-being scores.

(Education is the sole source/citation emitter -- see docs/agent-orchestration.md.)
"""
from __future__ import annotations

from typing import Iterator

from ..kb.retrieve import retrieve
from ..llm.base import Message
from ..llm.factory import get_llm
from .base import AgentContext, AgentEvent
from .style import CARE_RECIPIENT_TERMS, CAREGIVER_VOICE, safety_instruction

EMOTION_SYSTEM = (
    """You are I-Care, a warm, compassionate companion for dementia \
caregivers. The caregiver is sharing how they feel.

Rules:
- Open with one short sentence thanking them for sharing. Then validate the \
feelings they described (only those) and reassure \
them they are not alone. Caregiver guilt, grief, anger, and exhaustion are common \
and understandable.
- Recognise what their message shows about their strengths, such as reaching out \
or continuing to care while it is hard.
- Then offer one or two gentle, practical self-care suggestions. You may draw on \
the background notes below, but weave them in naturally -- do NOT use citation \
markers like [1].
- Be brief, warm, and human. Plain language, short paragraphs.
- Gently mention that support is available: Care2Caregivers helpline \
1-800-424-2494.
- If it fits, close by inviting them to choose one small thing they could do for \
themselves next.
- You are not a therapist. If they mention thoughts of self-harm or crisis, \
urge them to call or text 988 immediately.
"""
    + CAREGIVER_VOICE
    + CARE_RECIPIENT_TERMS
    + """

Background notes (self-care, for your reference only):
{context}"""
)


def _plain_context(hits) -> str:
    """Concatenate retrieved text WITHOUT citation numbers (silent grounding)."""
    return "\n\n".join(h.text for h in hits)


class EmotionSupportAgent:
    name = "emotion"

    def __init__(self, history_turns: int = 6) -> None:
        self._history_turns = history_turns

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        hits = retrieve(ctx.last_user_text(), k=3)
        system_content = safety_instruction(ctx.flags) + EMOTION_SYSTEM.format(context=_plain_context(hits))
        system = Message(role="system", content=system_content)
        prompt = [system, *ctx.recent(self._history_turns)]
        for delta in get_llm().stream_chat(prompt, temperature=0.6):
            yield ("delta", delta)
