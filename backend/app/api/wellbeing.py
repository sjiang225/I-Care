"""Retired automatic well-being API.

Keep a tombstone for older clients, with no database or identity lookup. In
particular, a guest-supplied session_id must never expose legacy account records.
Voluntary self-assessment will use a separate data model and API.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["wellbeing"])


@router.get("/wellbeing", deprecated=True, responses={410: {"description": "Feature retired"}})
def wellbeing() -> None:
    raise HTTPException(
        status_code=410,
        detail="Automatic well-being tracking has been retired.",
        headers={"Cache-Control": "no-store"},
    )
