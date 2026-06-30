"""Education Agent: grounded, citable answers from the Care2Caregivers KB.

Pattern: retrieve relevant chunks -> build a citation-aware context -> stream a
grounded answer. Emits the source documents so the UI can show citations.

This is the first M2 agent. The Coordinator + Emotion-Support agents are added
next and will route to / compose with this one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal

from ..config import get_settings
from ..kb.retrieve import retrieve
from ..llm.base import Message
from ..llm.factory import get_llm

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
(many caregivers are older adults).
- You are not a medical professional. For emergencies, urgent safety risks, or \
sudden changes, advise calling 911 or a doctor.

Reference material:
{context}"""


@dataclass
class Source:
    n: int
    title: str
    category: str
    url: str | None


EventType = Literal["sources", "delta"]


def _last_user_query(messages: list[Message]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _build_context_and_sources(hits) -> tuple[str, list[Source]]:
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
    def __init__(self, history_turns: int = 6) -> None:
        self._history_turns = history_turns

    def stream(self, messages: list[Message]) -> Iterator[tuple[EventType, object]]:
        settings = get_settings()
        query = _last_user_query(messages)

        hits = retrieve(query, k=max(settings.rag_top_k, 6))
        context, sources = _build_context_and_sources(hits)
        yield ("sources", sources)

        system = Message(
            role="system", content=EDUCATION_SYSTEM.format(context=context)
        )
        # Keep only the recent conversation turns to bound token usage.
        recent = [m for m in messages if m.role != "system"][-self._history_turns :]
        prompt = [system, *recent]

        for delta in get_llm().stream_chat(prompt, temperature=0.4):
            yield ("delta", delta)
