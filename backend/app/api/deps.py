"""Auth dependencies: resolve the current user from a Bearer token.

The user identity ALWAYS comes from the token, never from client-sent ids, so a
caller cannot read another user's data by changing an id.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from ..db import User, get_db


def current_user_optional(
    authorization: str | None = Header(default=None),
) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    return get_db().user_for_token(token)


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
