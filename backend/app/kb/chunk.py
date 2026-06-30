"""Split document text into overlapping, sentence-aware chunks with metadata.

PDF text extraction does not preserve reliable paragraph breaks, so we pack
whole sentences up to a target size (with overlap) rather than relying on
blank-line structure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    doc_id: str
    title: str
    category: str
    url: str | None
    index: int
    text: str

    def metadata(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "url": self.url,
            "index": self.index,
        }


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    # Normalize all whitespace/newlines to single spaces first.
    flat = re.sub(r"\s+", " ", text).strip()
    if not flat:
        return []
    parts = _SENTENCE_RE.split(flat)
    # Hard-wrap any monster "sentence" (e.g. bullet lists with no punctuation).
    out: list[str] = []
    for p in parts:
        if len(p) <= 1500:
            out.append(p)
        else:
            for i in range(0, len(p), 1200):
                out.append(p[i : i + 1200])
    return [s for s in (s.strip() for s in out) if s]


def chunk_text(
    text: str,
    *,
    doc_id: str,
    title: str,
    category: str,
    url: str | None,
    target_chars: int = 1000,
    overlap_sentences: int = 1,
) -> list[Chunk]:
    sentences = _split_sentences(text)
    if not sentences:
        return []

    raw_chunks: list[str] = []
    buf: list[str] = []
    size = 0

    for sent in sentences:
        if buf and size + len(sent) + 1 > target_chars:
            raw_chunks.append(" ".join(buf))
            # carry a little overlap for context continuity
            buf = buf[-overlap_sentences:] if overlap_sentences else []
            size = sum(len(s) + 1 for s in buf)
        buf.append(sent)
        size += len(sent) + 1

    if buf:
        raw_chunks.append(" ".join(buf))

    return [
        Chunk(
            doc_id=doc_id,
            title=title,
            category=category,
            url=url,
            index=i,
            text=c,
        )
        for i, c in enumerate(raw_chunks)
    ]
