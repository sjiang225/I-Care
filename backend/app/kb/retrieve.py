"""Retrieval: embed a query and fetch the most relevant knowledge-base chunks.

This is the read side used by the Education Agent (M2). It returns chunks with
their source metadata so answers can cite Care2Caregivers guides.
"""
from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from ..llm.factory import get_llm
from .store import LocalVectorStore, SearchHit


@lru_cache
def _store() -> LocalVectorStore:
    settings = get_settings()
    store = LocalVectorStore(settings.kb_db_path)
    recorded = store.get_meta("embed_model")
    if settings.llm_provider.lower() == "openai" and recorded and recorded != settings.openai_embed_model:
        raise RuntimeError(
            f"Knowledge base {settings.kb_db_path} was embedded with {recorded!r}, but "
            f"OPENAI_EMBED_MODEL is {settings.openai_embed_model!r}. Point KB_DB_PATH at a "
            "knowledge base built with the same model (see scripts/reembed_kb.py)."
        )
    return store


def retrieve(
    query: str, k: int | None = None, category: str | None = None
) -> list[SearchHit]:
    settings = get_settings()
    k = k or settings.rag_top_k
    query_vec = get_llm().embed([query])[0]
    return _store().search(query_vec, k=k, category=category)


def format_context(hits: list[SearchHit]) -> str:
    """Render hits as a numbered, citable context block for a prompt."""
    blocks = []
    for i, h in enumerate(hits, 1):
        title = h.metadata.get("title", "Care2Caregivers")
        blocks.append(f"[{i}] {title}\n{h.text}")
    return "\n\n".join(blocks)
