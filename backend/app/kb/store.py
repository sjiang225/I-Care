"""Vector store abstraction + a dependency-free local SQLite implementation.

The local store keeps M1 runnable with no external infra (no Postgres/Docker).
Production swaps in a PgVectorStore implementing the same VectorStore protocol;
nothing else in the app changes.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np


@dataclass
class Record:
    """A stored chunk: its text, source metadata, and embedding."""

    id: str  # f"{doc_id}:{index}"
    text: str
    metadata: dict
    embedding: list[float]


@dataclass
class SearchHit:
    text: str
    metadata: dict
    score: float


class VectorStore(Protocol):
    def reset(self) -> None: ...
    def add(self, records: list[Record]) -> None: ...
    def count(self) -> int: ...
    def search(
        self, query: list[float], k: int = 4, category: str | None = None
    ) -> list[SearchHit]: ...


class LocalVectorStore:
    """Brute-force cosine search over SQLite. Fine for the C2C corpus
    (a few hundred chunks); swap to pgvector when scaling up."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                metadata TEXT NOT NULL,
                embedding TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def reset(self) -> None:
        self._conn.execute("DELETE FROM chunks")
        self._conn.commit()

    def add(self, records: list[Record]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO chunks (id, text, metadata, embedding) "
            "VALUES (?, ?, ?, ?)",
            [
                (
                    r.id,
                    r.text,
                    json.dumps(r.metadata, ensure_ascii=False),
                    json.dumps(r.embedding),
                )
                for r in records
            ],
        )
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def search(
        self, query: list[float], k: int = 4, category: str | None = None
    ) -> list[SearchHit]:
        rows = self._conn.execute(
            "SELECT text, metadata, embedding FROM chunks"
        ).fetchall()
        if not rows:
            return []

        texts, metas, embs = [], [], []
        for text, meta_json, emb_json in rows:
            meta = json.loads(meta_json)
            if category and meta.get("category") != category:
                continue
            texts.append(text)
            metas.append(meta)
            embs.append(json.loads(emb_json))

        if not embs:
            return []

        matrix = np.asarray(embs, dtype=np.float32)
        q = np.asarray(query, dtype=np.float32)
        # cosine similarity
        matrix_n = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-8)
        q_n = q / (np.linalg.norm(q) + 1e-8)
        scores = matrix_n @ q_n

        top = np.argsort(scores)[::-1][:k]
        return [
            SearchHit(text=texts[i], metadata=metas[i], score=float(scores[i]))
            for i in top
        ]
