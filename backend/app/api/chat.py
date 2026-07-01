"""Chat API: streams answers from the multi-agent pipeline.

Routes every turn through the Coordinator, which runs a safety pre-check,
decides between the Education (RAG) and Emotion-Support agents, and streams a
grounded, empathetic answer with citations.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agents.base import AgentContext
from ..agents.coordinator import Coordinator
from ..agents.education import Source
from ..llm.base import Message

router = APIRouter(prefix="/api", tags=["chat"])

_coordinator = Coordinator()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str = "default"


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
    ctx = AgentContext(messages=_to_messages(req), session_id=req.session_id)

    def event_stream() -> Iterator[str]:
        try:
            for kind, payload in _coordinator.stream(ctx):
                if kind == "sources":
                    sources: list[Source] = payload  # type: ignore[assignment]
                    yield _sse("sources", {"sources": [asdict(s) for s in sources]})
                elif kind == "delta":
                    yield _sse("delta", {"text": payload})
                elif kind == "signal":
                    yield _sse("signal", payload)  # type: ignore[arg-type]
            yield _sse("done", {})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
