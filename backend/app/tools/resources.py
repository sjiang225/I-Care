"""NJ local-resources + Care2Caregivers videos.

Provides:
  * find_local_resources TOOL -> statewide helplines + county facilities.
  * pick_videos() helper -> topic-relevant videos by KB category.

Data files live in ./data (built by scripts/build_nj_facilities.py and curated).
See docs/nj-resources-and-videos.md.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..llm.base import ToolSpec
from .base import Tool, registry

_DATA = Path(__file__).parent / "data"


@lru_cache
def _facilities() -> list[dict]:
    return json.loads((_DATA / "nj_facilities.json").read_text("utf-8"))["facilities"]


@lru_cache
def _resources() -> list[dict]:
    return json.loads((_DATA / "nj_resources.json").read_text("utf-8"))["resources"]


@lru_cache
def _videos() -> list[dict]:
    return json.loads((_DATA / "videos.json").read_text("utf-8"))["videos"]


def _norm_county(s: str) -> str:
    return s.lower().replace("county", "").strip()


def pick_videos(category: str, limit: int = 2, language: str = "en") -> list[dict]:
    """Topic-relevant videos for a KB category (title + url only)."""
    hits = [
        {"title": v["title"], "url": v["url"]}
        for v in _videos()
        if v.get("language", "en") == language and v.get("category") == category
    ]
    return hits[:limit]


def get_local_resources(county: str | None = None, max_facilities: int = 8) -> dict:
    """Statewide helplines + (if county given) that county's facilities."""
    helplines = [
        {
            "name": r["name"],
            "phone": r["phone"],
            "url": r["url"],
            "description": r["description"],
        }
        for r in _resources()
    ]

    facilities: list[dict] = []
    if county:
        target = _norm_county(county)
        facilities = [
            {"name": f["name"], "city": f["city"], "county": f["county"]}
            for f in _facilities()
            if _norm_county(f["county"]) == target
        ][:max_facilities]

    return {
        "helplines": helplines,
        "facilities": facilities,
        "facilities_note": (
            "Facility listings have no direct contact info at the source; "
            "call a helpline above for a warm referral."
            if facilities
            else ""
        ),
    }


# ---- Tool registration ----

FIND_RESOURCES_SPEC = ToolSpec(
    name="find_local_resources",
    description=(
        "Find New Jersey caregiver resources: statewide support helplines and, "
        "if a county is provided, local dementia-care facilities to consider."
    ),
    parameters={
        "type": "object",
        "properties": {
            "county": {
                "type": "string",
                "description": "NJ county (e.g. 'Bergen') if the caregiver mentions a location.",
            },
            "resource_type": {
                "type": "string",
                "enum": ["helpline", "referral", "crisis", "facility", "any"],
                "description": "Kind of resource sought.",
            },
        },
    },
)


def _handle(args: dict, session_id: str) -> dict:
    return get_local_resources(county=args.get("county"))


registry.register(Tool(spec=FIND_RESOURCES_SPEC, handler=_handle))
