"""History API: a logged-in user's past conversations & messages."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import User, get_db
from .deps import current_user

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history")
def history(user: User = Depends(current_user)) -> dict:
    """Return the user's latest conversation (for restore-on-login)."""
    db = get_db()
    latest_id = db.latest_conversation(user.id)
    messages = (
        [
            {"role": m.role, "content": m.content}
            for m in db.conversation_messages(latest_id)
        ]
        if latest_id
        else []
    )
    return {"latest_conversation_id": latest_id, "latest_messages": messages}
