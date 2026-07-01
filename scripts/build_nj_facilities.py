"""Build backend/app/tools/data/nj_facilities.json from carenewjersey.org.

Fetches the NJ Alzheimer's/dementia facilities list, parses (city, name, county),
cleans out obvious non-care-facility noise, dedupes, and writes JSON. Prints the
removed entries so the noise filter can be reviewed (see docs section 8).

Run:  python scripts/build_nj_facilities.py

Source note: the site provides NO contact info, and its "Alzheimer's / dementia /
short-term memory" type label is applied in a rotating way, so we DROP that field.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://www.carenewjersey.org/list02_new_jersey_Alzheimers_facilities.htm"
OUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "backend/app/tools/data/nj_facilities.json"
)

# Row format: "<City> NJ - New Jersey <type> facilities -- <Name>, <County> County"
ROW_RE = re.compile(
    r"^(?P<city>[A-Za-z .'\-]+?)\s+NJ\s*-\s*New Jersey.*?facilities\s*--\s*"
    r"(?P<name>.+?),\s*(?P<county>[A-Za-z .]+?)\s+County",
)

# Names matching these are janitorial / facility-services / staffing / media firms
# or garbled rows, not dementia care facilities. Reviewed manually vs the source.
NOISE_PATTERNS = [
    r"\bfacilit(y|ies)\b.*\b(service|services|srvs|integ\w*|manage\w*|mang\w*)\b",
    r"\b(service|services|srvs|integ\w*|manage\w*|mang\w*)\b.*\bfacilit",
    r"\bairmark\b",
    r"\baramark\b",
    r"\bmagazine\b",
    r"\bjrnl\b",
    r"janitorial",
    r"cleaning",
    r"\bstaffing\b",
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

# Navigation/link text that leaks into the front of some parsed names.
NAV_PREFIXES = [
    "Contact Community Learn More ",
    "Learn More ",
    "Click to request assistance ",
]


def clean_name(name: str) -> str:
    for prefix in NAV_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip(" -,")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return resp.read().decode("latin-1")


def parse(html_text: str) -> list[dict]:
    text = html.unescape(re.sub(r"<[^>]+>", " ", html_text))
    rows: list[dict] = []
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        m = ROW_RE.match(line)
        if not m:
            continue
        rows.append(
            {
                "name": clean_name(m.group("name")),
                "city": m.group("city").strip(),
                "county": m.group("county").strip(),
            }
        )
    return rows


def main() -> None:
    raw = parse(fetch(SOURCE_URL))

    kept: list[dict] = []
    removed: list[dict] = []
    seen: set[tuple] = set()
    for r in raw:
        if NOISE_RE.search(r["name"]):
            removed.append(r)
            continue
        key = (r["name"].lower(), r["city"].lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(r)

    kept.sort(key=lambda r: (r["county"], r["city"], r["name"]))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "source": SOURCE_URL,
                "fetched": "2026-07-01",
                "note": (
                    "Source provides no contact info; its care-type label is "
                    "unreliable and dropped. Noise entries removed (see removed_log)."
                ),
                "removed_log": removed,
                "facilities": kept,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"parsed={len(raw)}  kept={len(kept)}  removed={len(removed)}")
    print(f"wrote {OUT_PATH}")
    if removed:
        print("--- removed (noise) ---")
        for r in removed:
            print(f"  - {r['name']} ({r['city']}, {r['county']})")
    if len(kept) < 20:
        print("WARNING: suspiciously few rows parsed; check page format.", file=sys.stderr)


if __name__ == "__main__":
    main()
