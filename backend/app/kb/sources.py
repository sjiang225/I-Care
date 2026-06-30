"""Load the Care2Caregivers source manifest (sources.json)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_SOURCES_PATH = Path(__file__).parent / "sources.json"


@dataclass(frozen=True)
class SourceDoc:
    id: str
    title: str
    category: str
    url_en: str | None
    url_es: str | None


def load_sources() -> list[SourceDoc]:
    data = json.loads(_SOURCES_PATH.read_text(encoding="utf-8"))
    return [
        SourceDoc(
            id=d["id"],
            title=d["title"],
            category=d["category"],
            url_en=d.get("url_en"),
            url_es=d.get("url_es"),
        )
        for d in data["documents"]
    ]
