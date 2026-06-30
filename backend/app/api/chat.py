"""Chat API: streams answers from the agent pipeline.

M2 (current): routes to the Education Agent (RAG over Care2Caregivers) and
streams a grounded, citable answer. The Coordinator + Emotion-Support agents
will be layered in next.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agents.education import EducationAgent, Source
from ..llm.base import Message

router = APIRouter(prefix="/api", tags=["chat"])

_education = EducationAgent()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _to_messages(req: ChatRequest) -> list[Message]:
    out: list[Message] = []
    for m in req.messages:
        role = m.role if m.role in ("user", "assistant", "system") else "user"
        out.append(Message(role=role, content=m.content))  # type: ignore[arg-type]
    return out


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    messages = _to_messages(req)

    def event_stream() -> Iterator[str]:
        try:
            for kind, payload in _education.stream(messages):
                if kind == "sources":
                    sources: list[Source] = payload  # type: ignore[assignment]
                    yield _sse("sources", {"sources": [asdict(s) for s in sources]})
                elif kind == "delta":
                    yield _sse("delta", {"text": payload})
            yield _sse("done", {})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
