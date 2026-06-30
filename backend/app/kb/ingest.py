"""Ingestion pipeline: sources -> download -> extract -> chunk -> embed -> store.

Run as a one-off script to (re)build the knowledge base:

    python -m app.kb.ingest            # ingest all docs
    python -m app.kb.ingest --limit 3  # quick test with 3 docs

Embeddings use the configured LLM provider (GPT in production; the mock
provider produces placeholder vectors so the pipeline runs without a key).
"""
from __future__ import annotations

import argparse
import sys

from ..config import get_settings
from ..llm.factory import get_llm
from .chunk import Chunk, chunk_text
from .extract import download_pdf, extract_text
from .sources import SourceDoc, load_sources
from .store import LocalVectorStore, Record


def _embed_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    llm = get_llm()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        out.extend(llm.embed(texts[i : i + batch_size]))
    return out


def build_chunks(docs: list[SourceDoc]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        if not doc.url_en:
            print(f"  ! skip {doc.id} (no English URL)")
            continue
        try:
            pdf = download_pdf(doc.url_en)
            text = extract_text(pdf)
        except Exception as exc:
            print(f"  ! failed {doc.id}: {exc}")
            continue
        doc_chunks = chunk_text(
            text,
            doc_id=doc.id,
            title=doc.title,
            category=doc.category,
            url=doc.url_en,
        )
        print(f"  + {doc.id}: {len(text)} chars -> {len(doc_chunks)} chunks")
        chunks.extend(doc_chunks)
    return chunks


def ingest(limit: int | None = None) -> int:
    settings = get_settings()
    docs = load_sources()
    if limit:
        docs = docs[:limit]

    print(f"Ingesting {len(docs)} document(s) using provider={settings.llm_provider}")
    chunks = build_chunks(docs)
    if not chunks:
        print("No chunks produced; aborting.")
        return 0

    print(f"Embedding {len(chunks)} chunks…")
    vectors = _embed_batch([c.text for c in chunks])

    records = [
        Record(
            id=f"{c.doc_id}:{c.index}",
            text=c.text,
            metadata=c.metadata(),
            embedding=v,
        )
        for c, v in zip(chunks, vectors)
    ]

    store = LocalVectorStore(settings.kb_db_path)
    store.reset()
    store.add(records)
    print(f"Stored {store.count()} chunks -> {settings.kb_db_path}")
    return store.count()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the I-Care knowledge base")
    parser.add_argument("--limit", type=int, default=None, help="ingest only N docs")
    args = parser.parse_args()
    n = ingest(limit=args.limit)
    sys.exit(0 if n > 0 else 1)


if __name__ == "__main__":
    main()
