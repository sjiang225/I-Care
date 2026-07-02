"""Chat API: streams answers from the multi-agent pipeline.

Auth is optional:
  * Logged-in user  -> data keyed by the user; messages persisted to a conversation.
  * Guest           -> data keyed by the client-sent session_id; nothing persisted.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agents.base import AgentContext
from ..agents.coordinator import Coordinator
from ..agents.education import Source
from ..db import User, get_db
from ..llm.base import Message
from .deps import current_user_optional

router = APIRouter(prefix="/api", tags=["chat"])

_coordinator = Coordinator()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str = "default"  # used for GUESTS only
    conversation_id: int | None = None  # used for logged-in users


def _to_messages(req: ChatRequest) -> list[Message]:
    out: list[Message] = []
    for m in req.messages:
        role = m.role if m.role in ("user", "assistant", "system") else "user"
        out.append(Message(role=role, content=m.content))  # type: ignore[arg-type]
    return out


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat(
    req: ChatRequest, user: User | None = Depends(current_user_optional)
) -> StreamingResponse:
    db = get_db()
    messages = _to_messages(req)
    last_user_text = next(
        (m.content for m in reversed(messages) if m.role == "user"), ""
    )

    # Determine the owner key + (for users) the conversation to persist into.
    conversation_id: int | None = None
    if user is not None:
        owner_key = f"u:{user.id}"
        conversation_id = req.conversation_id or db.create_conversation(
            user.id, title=last_user_text[:60]
        )
        db.add_message(conversation_id, user.id, "user", last_user_text)
    else:
        owner_key = req.session_id

    ctx = AgentContext(messages=messages, session_id=owner_key)

    def event_stream() -> Iterator[str]:
        if conversation_id is not None:
            yield _sse("meta", {"conversation_id": conversation_id})
        full = ""
        try:
            for kind, payload in _coordinator.stream(ctx):
                if kind == "sources":
                    sources: list[Source] = payload  # type: ignore[assignment]
                    yield _sse("sources", {"sources": [asdict(s) for s in sources]})
                elif kind == "delta":
                    full += payload  # type: ignore[operator]
                    yield _sse("delta", {"text": payload})
                elif kind == "resources":
                    yield _sse("resources", payload)  # type: ignore[arg-type]
                elif kind == "signal":
                    yield _sse("signal", payload)  # type: ignore[arg-type]
            yield _sse("done", {})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
        finally:
            if user is not None and conversation_id is not None and full:
                db.add_message(conversation_id, user.id, "assistant", full)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
