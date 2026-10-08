"""Application database (SQLite for now; swap to Postgres alongside pgvector).

Stores accounts, conversations, and explicitly submitted self-assessments.
Legacy inferred well-being records are retained in place, but no application
reader or writer uses them. Voluntary assessments have a separate data model.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .config import get_settings


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
    sources: list[dict] = field(default_factory=list)


class Database:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI may touch it from worker threads.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        # Preserve the legacy table/schema without deleting or migrating data.
        # Automatic recording and application access were retired in step 1.
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
            CREATE TABLE IF NOT EXISTS self_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                submission_id TEXT NOT NULL,
                instrument_id TEXT NOT NULL,
                instrument_version TEXT NOT NULL,
                answers TEXT NOT NULL,
                difficulty INTEGER,
                result TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(user_id, submission_id)
            );
            CREATE INDEX IF NOT EXISTS idx_assessment_user ON self_assessments(user_id, id);
            """
        )
        # Additive migration: old answers have no recoverable citation mapping.
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(messages)")}
        if "sources" not in columns:
            self._conn.execute("ALTER TABLE messages ADD COLUMN sources TEXT NOT NULL DEFAULT '[]'")
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
        self, conversation_id: int, user_id: int, role: str, content: str,
        sources: list[dict] | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO messages (conversation_id, user_id, role, content, created_at, sources)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, user_id, role, content, time.time(), json.dumps(sources or [])),
        )
        self._conn.commit()

    def conversation_messages(self, conversation_id: int) -> list["MessageRow"]:
        rows = self._conn.execute(
            "SELECT role, content, created_at, sources FROM messages"
            " WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [MessageRow(role=r[0], content=r[1], ts=r[2], sources=json.loads(r[3])) for r in rows]

    def owns_conversation(self, conversation_id: int, user_id: int) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone() is not None

    # ---- Voluntary self-assessment (never used by chat agents) ----

    def save_assessment(
        self, user_id: int, submission_id: str, answers: list[int],
        difficulty: int | None, result: dict,
    ) -> dict:
        encoded_answers = json.dumps(answers)
        self._conn.execute(
            "INSERT OR IGNORE INTO self_assessments"
            " (user_id, submission_id, instrument_id, instrument_version, answers, difficulty, result, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, submission_id, result["instrument_id"], result["instrument_version"],
             encoded_answers, difficulty, json.dumps(result), time.time()),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id, created_at, instrument_id, instrument_version, answers, difficulty, result"
            " FROM self_assessments WHERE user_id = ? AND submission_id = ?",
            (user_id, submission_id),
        ).fetchone()
        # Safe to retry after a lost response, but never overwrite an earlier result.
        if (row[2], row[3], row[4], row[5]) != (
            result["instrument_id"], result["instrument_version"], encoded_answers, difficulty,
        ):
            raise ValueError("This submission was already saved with different answers. Start a new assessment.")
        return {**json.loads(row[6]), "id": row[0], "created_at": row[1], "saved": True}

    def assessment_history(self, user_id: int, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, created_at, result FROM self_assessments"
            " WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit),
        ).fetchall()
        return [{**json.loads(r[2]), "id": r[0], "created_at": r[1], "saved": True} for r in rows]


@lru_cache
def get_db() -> Database:
    return Database(get_settings().app_db_path)
