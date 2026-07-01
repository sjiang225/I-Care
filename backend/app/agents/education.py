"""Education Agent: grounded, citable answers from the Care2Caregivers KB.

Pattern: retrieve relevant chunks -> build a citation-aware context -> stream a
grounded answer. Emits the source documents so the UI can show citations.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterator

from ..config import get_settings
from ..kb.retrieve import retrieve
from ..llm.base import Message
from ..llm.factory import get_llm
from ..tools.resources import pick_videos
from .base import AgentContext, AgentEvent

EDUCATION_SYSTEM = """You are I-Care, a warm, patient companion for dementia \
caregivers. Answer the caregiver's question using ONLY the Care2Caregivers \
reference material provided below.

Rules:
- Base every factual claim on the reference material. Cite sources inline like \
[1] or [2], matching the numbered references.
- If the material does not cover the question, say so honestly, give only \
general, safe guidance, and suggest contacting the Care2Caregivers helpline or \
their doctor. Never invent facts or citations.
- Be empathetic and practical. Use plain, simple language and short paragraphs \
(many caregivers are older adults).{tone}
- You are not a medical professional. For emergencies, urgent safety risks, or \
sudden changes, advise calling 911 or a doctor.

Reference material:
{context}"""

_EMOTION_TONE = (
    "\n- The caregiver also sounds emotionally stressed. Open with one short, "
    "warm sentence acknowledging their feelings before the practical guidance."
)


@dataclass
class Source:
    n: int
    title: str
    category: str
    url: str | None


def build_context_and_sources(hits) -> tuple[str, list[Source]]:
    """Number unique source documents; label each chunk with its doc number."""
    doc_num: dict[str, int] = {}
    sources: list[Source] = []
    blocks: list[str] = []

    for h in hits:
        doc_id = h.metadata.get("doc_id", h.metadata.get("title", "?"))
        if doc_id not in doc_num:
            n = len(doc_num) + 1
            doc_num[doc_id] = n
            sources.append(
                Source(
                    n=n,
                    title=h.metadata.get("title", "Care2Caregivers"),
                    category=h.metadata.get("category", ""),
                    url=h.metadata.get("url"),
                )
            )
        blocks.append(f"[{doc_num[doc_id]}] {h.text}")

    return "\n\n".join(blocks), sources


class EducationAgent:
    name = "education"

    def __init__(self, history_turns: int = 6) -> None:
        self._history_turns = history_turns

    def stream(self, ctx: AgentContext) -> Iterator[AgentEvent]:
        settings = get_settings()
        hits = retrieve(ctx.last_user_text(), k=max(settings.rag_top_k, 6))
        context, sources = build_context_and_sources(hits)
        yield ("sources", sources)

        # Assemble local resources (from the router) + topic-relevant videos.
        extras = self._resources_payload(ctx, hits)
        if extras:
            yield ("resources", extras)

        # Add an empathetic lead-in when emotional distress is present OR the
        # well-being trend shows high stress — and the Emotion agent hasn't
        # already handled empathy this turn (composition).
        needs_empathy = (
            ctx.flags.get("needs_emotion") or ctx.flags.get("high_stress")
        ) and not ctx.flags.get("empathy_done")
        tone = _EMOTION_TONE if needs_empathy else ""
        if ctx.flags.get("caregiver_state") and not ctx.flags.get("empathy_done"):
            tone += "\n- " + ctx.flags["caregiver_state"]
        if extras:
            tone += (
                "\n- Local NJ resources and/or a short related video are shown "
                "below your answer; you may briefly invite them to look."
            )
        system = Message(
            role="system",
            content=EDUCATION_SYSTEM.format(context=context, tone=tone),
        )
        prompt = [system, *ctx.recent(self._history_turns)]

        for delta in get_llm().stream_chat(prompt, temperature=0.4):
            yield ("delta", delta)

    def _resources_payload(self, ctx: AgentContext, hits) -> dict | None:
        """Helplines/facilities (from router flags) + topic videos, or None."""
        res = ctx.flags.get("resources") or {}
        categories = Counter(
            h.metadata.get("category") for h in hits if h.metadata.get("category")
        )
        dominant = categories.most_common(1)[0][0] if categories else None
        videos = pick_videos(dominant) if dominant else []

        # Under high stress, also surface a self-care video regardless of topic.
        extra_cat = ctx.flags.get("extra_video_category")
        if extra_cat:
            urls = {v["url"] for v in videos}
            for v in pick_videos(extra_cat, limit=1):
                if v["url"] not in urls:
                    videos.append(v)

        payload = {
            "helplines": res.get("helplines", []),
            "facilities": res.get("facilities", []),
            "facilities_note": res.get("facilities_note", ""),
            "videos": videos,
        }
        if payload["helplines"] or payload["facilities"] or payload["videos"]:
            return payload
        return None
