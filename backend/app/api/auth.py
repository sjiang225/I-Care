"""Authentication API: register / login / logout / me.

Prototype-grade (see docs/user-accounts.md). Passwords are stored hashed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from ..auth.security import hash_password, new_token, verify_password
from ..db import User, get_db
from .deps import current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterReq(BaseModel):
    email: str
    password: str
    display_name: str = ""


class LoginReq(BaseModel):
    email: str
    password: str


def _issue(user: User) -> dict:
    token = new_token()
    get_db().create_token(user.id, token)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
        },
    }


@router.post("/register")
def register(req: RegisterReq) -> dict:
    db = get_db()
    email = req.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if db.get_user_auth(email):
        raise HTTPException(status_code=409, detail="This email is already registered.")
    salt, pw_hash = hash_password(req.password)
    name = req.display_name.strip() or email.split("@")[0]
    user = db.create_user(email, pw_hash, salt, name)
    return _issue(user)


@router.post("/login")
def login(req: LoginReq) -> dict:
    rec = get_db().get_user_auth(req.email.strip().lower())
    if not rec or not verify_password(req.password, rec["salt"], rec["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _issue(
        User(id=rec["id"], email=rec["email"], display_name=rec["display_name"])
    )


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    if authorization and authorization.lower().startswith("bearer "):
        get_db().delete_token(authorization[7:].strip())
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"id": user.id, "email": user.email, "display_name": user.display_name}
