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


@dataclass
class User:
    id: int
    email: str
    display_name: str


@dataclass
class MessageRow:
    role: str
    content: str
    ts: float


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
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at REAL NOT NULL,
                title TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
            CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
            """
        )
        self._conn.commit()

    # ---- Users & auth ----

    def create_user(
        self, email: str, password_hash: str, salt: str, display_name: str
    ) -> "User":
        cur = self._conn.execute(
            "INSERT INTO users (email, password_hash, salt, display_name, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (email.lower(), password_hash, salt, display_name, time.time()),
        )
        self._conn.commit()
        return User(id=cur.lastrowid, email=email.lower(), display_name=display_name)

    def get_user_auth(self, email: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, email, display_name, password_hash, salt FROM users"
            " WHERE email = ?",
            (email.lower(),),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "email": row[1],
            "display_name": row[2],
            "password_hash": row[3],
            "salt": row[4],
        }

    def create_token(self, user_id: int, token: str, ttl_days: int = 30) -> None:
        now = time.time()
        self._conn.execute(
            "INSERT INTO auth_tokens (token, user_id, created_at, expires_at)"
            " VALUES (?, ?, ?, ?)",
            (token, user_id, now, now + ttl_days * 86400),
        )
        self._conn.commit()

    def user_for_token(self, token: str) -> "User | None":
        row = self._conn.execute(
            "SELECT u.id, u.email, u.display_name FROM auth_tokens t"
            " JOIN users u ON u.id = t.user_id"
            " WHERE t.token = ? AND t.expires_at > ?",
            (token, time.time()),
        ).fetchone()
        return User(id=row[0], email=row[1], display_name=row[2]) if row else None

    def delete_token(self, token: str) -> None:
        self._conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        self._conn.commit()

    # ---- Conversations & messages ----

    def create_conversation(self, user_id: int, title: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO conversations (user_id, created_at, title) VALUES (?, ?, ?)",
            (user_id, time.time(), title),
        )
        self._conn.commit()
        return cur.lastrowid

    def latest_conversation(self, user_id: int) -> int | None:
        row = self._conn.execute(
            "SELECT id FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return row[0] if row else None

    def add_message(
        self, conversation_id: int, user_id: int, role: str, content: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO messages (conversation_id, user_id, role, content, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (conversation_id, user_id, role, content, time.time()),
        )
        self._conn.commit()

    def conversation_messages(self, conversation_id: int) -> list["MessageRow"]:
        rows = self._conn.execute(
            "SELECT role, content, created_at FROM messages"
            " WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [MessageRow(role=r[0], content=r[1], ts=r[2]) for r in rows]

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
