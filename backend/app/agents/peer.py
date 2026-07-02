"""Peer-Support Agent: a "virtual peer" companion for connection & normalization.

Care2Caregivers is itself a peer-support helpline, so peer support here means the
feeling of being understood by someone who gets caregiving -- belonging and
normalization, NOT clinical advice.

ETHICS (do not relax):
  * Transparent: an AI companion reflecting COMMON caregiver experiences, never a
    real person. The UI also labels peer messages (see Chat.tsx).
  * Collective voice ("many caregivers feel...") -- NEVER a fabricated personal
    life story presented as real.
  * Crisis still routes through the safety guardrail; no medical claims.
"""
from __future__ import annotations

from typing import Iterator

from ..kb.retrieve import retrieve
from ..llm.base import Message
from ..llm.factory import get_llm
from .base import AgentContext, AgentEvent
from .wellbeing_logging import assess_and_log_wellbeing

PEER_SYSTEM = """You are the Peer Companion in I-Care — a warm AI companion that \
reflects the shared experiences of family caregivers of people with dementia.

Your role is CONNECTION and NORMALIZATION, not clinical advice:
- Help them feel less alone. Gently normalize what they feel — so many caregivers \
go through the very same thing.
- Use COLLECTIVE, peer language ("many of us who've cared for someone have felt \
this", "you're not the only one"). NEVER invent a specific personal life story or \
claim to be a real human being.
- If asked, be honest that you are an AI companion reflecting what caregivers \
commonly share.
- Offer warm encouragement and, if it fits, one small practical idea (you may draw \
on the notes below — weave in naturally, no [n] citations).
- Keep it brief and human. If they mention self-harm or crisis, urge them to call \
or text 988 right away. Real peer supporters are also at Care2Caregivers: \
1-800-424-2494.

Background notes (self-care, for your reference only):
{context}"""


class PeerSupportAgent:
    name = "peer"

    def __init__(self, history_turns: int = 6) -> None:
        self._history_turns = history_turns

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        # Peer chats are emotional too -> track well-being (shared helper).
        logged = assess_and_log_wellbeing(ctx, self._history_turns)
        if logged:
            yield ("signal", {"wellbeing": logged})
        # Tell the UI to badge this turn as a transparent peer interaction.
        yield ("signal", {"agent": "peer"})

        hits = retrieve(ctx.last_user_text(), k=3)
        context = "\n\n".join(h.text for h in hits)
        system_content = PEER_SYSTEM.format(context=context)
        if ctx.flags.get("caregiver_state"):
            system_content += "\n\n" + ctx.flags["caregiver_state"]

        prompt = [Message(role="system", content=system_content), *ctx.recent(self._history_turns)]
        for delta in get_llm().stream_chat(prompt, temperature=0.75):
            yield ("delta", delta)
