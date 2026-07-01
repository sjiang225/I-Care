"""Well-being API: read the caregiver's stress/emotion trend for a session.

Powers the trend visualization (see docs/wellbeing-visualization.md). Data is
written by the Emotion agent's log_wellbeing tool.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..db import get_db

router = APIRouter(prefix="/api", tags=["wellbeing"])


@router.get("/wellbeing")
def wellbeing(session_id: str = "default", limit: int = 30) -> dict:
    db = get_db()
    asc = list(reversed(db.wellbeing_trend(session_id, limit)))  # oldest -> newest
    summary = db.wellbeing_summary(session_id, limit)
    return {
        "session_id": session_id,
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
