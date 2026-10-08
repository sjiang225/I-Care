"""Re-embed the existing knowledge base with another embedding model.

Chunk text and source metadata are copied unchanged from --src; only the vectors
are recomputed, so no PDFs are downloaded again. The source file is never
modified, and a labelled backup of it is kept, so switching back is just a
KB_DB_PATH / OPENAI_EMBED_MODEL change in .env.

    cd backend
    # .env already points OPENAI_BASE_URL / OPENAI_API_KEY at the new provider
    .venv/bin/python scripts/reembed_kb.py --model gemini-embedding-001 \
        --dest data/kb.gemini.sqlite3

Afterwards set in .env:  KB_DB_PATH=data/kb.gemini.sqlite3
                         OPENAI_EMBED_MODEL=gemini-embedding-001
To switch back:          KB_DB_PATH=data/kb.openai.sqlite3
                         OPENAI_EMBED_MODEL=text-embedding-3-small  (plus the OpenAI URL/key)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.kb.store import LocalVectorStore, Record  # noqa: E402
from app.llm.openai_provider import OpenAIProvider  # noqa: E402

ORIGINAL_MODEL = "text-embedding-3-small"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="data/kb.sqlite3")
    parser.add_argument("--dest", required=True)
    parser.add_argument("--model", required=True, help="Embedding model for the new vectors")
    parser.add_argument("--backup", default="data/kb.openai.sqlite3",
                        help=f"Copy of --src, labelled as {ORIGINAL_MODEL} if unlabelled")
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()

    src, dest = Path(args.src), Path(args.dest)
    if src.resolve() == dest.resolve():
        sys.exit("--dest must differ from --src; the original is kept untouched.")

    backup = Path(args.backup)
    if not backup.exists():
        shutil.copy2(src, backup)
        store = LocalVectorStore(backup)
        if not store.get_meta("embed_model"):
            store.set_meta("embed_model", ORIGINAL_MODEL)
        print(f"Backup: {backup} ({store.count()} chunks, {store.get_meta('embed_model')})")

    rows = sqlite3.connect(src).execute("SELECT id, text, metadata FROM chunks ORDER BY id").fetchall()
    settings = get_settings()
    provider = OpenAIProvider(api_key=settings.openai_api_key, base_url=settings.openai_base_url,
                              chat_model=settings.openai_chat_model, embed_model=args.model)

    records: list[Record] = []
    for start in range(0, len(rows), args.batch):
        batch = rows[start:start + args.batch]
        vectors = provider.embed([text for _, text, _ in batch])
        records += [Record(id=i, text=t, metadata=json.loads(m), embedding=v)
                    for (i, t, m), v in zip(batch, vectors)]
        print(f"  embedded {len(records)}/{len(rows)}", flush=True)

    tmp = dest.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    out = LocalVectorStore(tmp)
    out.add(records)
    out.set_meta("embed_model", args.model)
    count, dim = out.count(), len(records[0].embedding)
    del out
    tmp.replace(dest)
    print(f"Wrote {dest}: {count} chunks, {dim}-dim vectors from {args.model}")


if __name__ == "__main__":
    main()
