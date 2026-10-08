"""Public catalogue of the existing educational guides and curated videos."""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter

from ..kb.sources import load_sources
from ..tools.resources import load_videos

router = APIRouter(prefix="/api", tags=["library"])

CATEGORY_LABELS = {
    "activities": "Activities and engagement",
    "understanding_dementia": "Understanding dementia",
    "communication": "Communication",
    "challenging_behaviors": "Changes in behavior",
    "incontinence": "Incontinence",
    "nutrition": "Eating and nutrition",
    "sleep": "Sleep",
    "recognition": "Recognition and memory",
    "care_options": "Care options and planning",
    "caregiver_selfcare": "Caring for yourself",
    "about": "About support services",
}


def _web_url(url: str | None) -> str | None:
    try:
        parsed = urlsplit(url or "")
        if parsed.scheme in ("https", "http") and parsed.netloc and not parsed.username and not parsed.password:
            return url
    except ValueError:
        pass
    return None


@router.get("/library")
def library() -> dict:
    documents = []
    for source in load_sources():
        documents.append({
            "id": source.id, "title": source.title, "category": source.category,
            "url": _web_url(source.url_en),
        })
    # Unlike chat's short English recommendations, browsing includes every video.
    videos = [{
        "id": video["youtube_id"], "title": video["title"],
        "category": video["category"], "language": video.get("language", "en"),
        "url": _web_url(video.get("url")),
    } for video in load_videos()]
    # Include new manifest categories without silently dropping their documents.
    used = {item["category"] for item in [*documents, *videos]}
    order = [key for key in CATEGORY_LABELS if key in used]
    order += sorted(used - set(order))
    return {
        "documents": documents,
        "videos": videos,
        "categories": [{"id": key, "label": CATEGORY_LABELS.get(key, key.replace("_", " ").title())}
                       for key in order],
    }
