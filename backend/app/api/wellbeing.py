"""Well-being API: read the caregiver's stress/emotion trend.

Logged-in user -> their own trend (keyed by user). Guest -> by session_id.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import User, get_db
from .deps import current_user_optional

router = APIRouter(prefix="/api", tags=["wellbeing"])


@router.get("/wellbeing")
def wellbeing(
    session_id: str = "default",
    limit: int = 30,
    user: User | None = Depends(current_user_optional),
) -> dict:
    db = get_db()
    key = f"u:{user.id}" if user is not None else session_id
    asc = list(reversed(db.wellbeing_trend(key, limit)))  # oldest -> newest
    summary = db.wellbeing_summary(key, limit)
    return {
        "session_id": key,
        "points": [
            {
                "ts": l.ts,
                "stress_level": l.stress_level,
                "emotions": l.emotions,
                "note": l.note,
            }
            for l in asc
        ],
        "summary": {
            "count": summary.count,
            "avg_stress": summary.avg_stress,
            "latest_stress": summary.latest_stress,
            "trend": summary.trend,
            "top_emotions": summary.top_emotions,
        },
    }
