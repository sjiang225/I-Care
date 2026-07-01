"""Application database (SQLite for now; swap to Postgres alongside pgvector).

Currently holds the caregiver well-being log that powers the proposal's
"track caregiver stress patterns over time" requirement.
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import get_settings


@dataclass
class WellbeingLog:
    session_id: str
    ts: float
    stress_level: int  # 1..5
    emotions: list[str]
    note: str


@dataclass
class WellbeingSummary:
    count: int
    avg_stress: float
    latest_stress: int | None
    trend: str  # "up" | "down" | "steady" (rising stress = "up")
    top_emotions: list[tuple[str, int]]


class Database:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI may touch it from worker threads.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wellbeing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                ts REAL NOT NULL,
                stress_level INTEGER NOT NULL,
                emotions TEXT NOT NULL,
                note TEXT
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_wb_session ON wellbeing_logs(session_id)"
        )
        self._conn.commit()

    def add_wellbeing(
        self, session_id: str, stress_level: int, emotions: list[str], note: str = ""
    ) -> WellbeingLog:
        log = WellbeingLog(
            session_id=session_id,
            ts=time.time(),
            stress_level=max(1, min(5, int(stress_level))),
            emotions=emotions,
            note=note,
        )
        self._conn.execute(
            "INSERT INTO wellbeing_logs (session_id, ts, stress_level, emotions, note)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                log.session_id,
                log.ts,
                log.stress_level,
                json.dumps(log.emotions, ensure_ascii=False),
                log.note,
            ),
        )
        self._conn.commit()
        return log

    def wellbeing_trend(self, session_id: str, limit: int = 30) -> list[WellbeingLog]:
        """Return logs newest-first (most recent `limit` entries)."""
        rows = self._conn.execute(
            "SELECT session_id, ts, stress_level, emotions, note FROM wellbeing_logs"
            " WHERE session_id = ? ORDER BY ts DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [
            WellbeingLog(
                session_id=r[0],
                ts=r[1],
                stress_level=r[2],
                emotions=json.loads(r[3]),
                note=r[4] or "",
            )
            for r in rows
        ]

    def wellbeing_summary(
        self, session_id: str, limit: int = 30
    ) -> WellbeingSummary:
        """Aggregate the recent trend: count, average, latest, direction, emotions."""
        asc = list(reversed(self.wellbeing_trend(session_id, limit)))  # oldest->newest
        if not asc:
            return WellbeingSummary(0, 0.0, None, "steady", [])

        stresses = [l.stress_level for l in asc]
        count = len(stresses)
        avg = round(sum(stresses) / count, 2)
        latest = stresses[-1]

        # Trend: compare the later half's mean stress against the earlier half's.
        trend = "steady"
        if count >= 4:
            half = count // 2
            earlier = stresses[:half]
            later = stresses[half:]
            diff = (sum(later) / len(later)) - (sum(earlier) / len(earlier))
            trend = "up" if diff > 0.5 else "down" if diff < -0.5 else "steady"

        counter = Counter(e for l in asc for e in l.emotions)
        top = counter.most_common(5)
        return WellbeingSummary(count, avg, latest, trend, top)


@lru_cache
def get_db() -> Database:
    return Database(get_settings().app_db_path)
