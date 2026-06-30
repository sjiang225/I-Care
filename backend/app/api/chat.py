"""Chat API: a thin streaming endpoint over the configured LLM provider.

M0 scaffold: routes straight to the LLM. In M2 this is replaced by the
Coordinator -> {Education, Emotion-Support} multi-agent pipeline (with RAG).
"""
from __future__ import annotations

import json
from typing import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..llm.base import Message
from ..llm.factory import get_llm

router = APIRouter(prefix="/api", tags=["chat"])

SYSTEM_PROMPT = (
    "You are I-Care, a warm, patient digital companion for dementia caregivers. "
    "Give clear, practical, evidence-based guidance. Be empathetic and concise. "
    "You are not a medical professional; encourage contacting a doctor or 911 "
    "for emergencies."
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _build_messages(req: ChatRequest) -> list[Message]:
    msgs = [Message(role="system", content=SYSTEM_PROMPT)]
    for m in req.messages:
        role = m.role if m.role in ("user", "assistant", "system") else "user"
        msgs.append(Message(role=role, content=m.content))  # type: ignore[arg-type]
    return msgs


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    llm = get_llm()
    messages = _build_messages(req)

    def event_stream() -> Iterator[str]:
        try:
            for delta in llm.stream_chat(messages):
                yield _sse("delta", {"text": delta})
            yield _sse("done", {})
        except Exception as exc:  # surface errors to the client cleanly
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
