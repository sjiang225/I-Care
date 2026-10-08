"""Scenario check for R06 (supportive tone) and R07 (neutral care-recipient wording).

Runs a fixed set of caregiver messages through the real Coordinator (same route,
agents and LLM as the app) and applies simple automated checks. Nothing is written
to the app database. Uses the configured LLM, so it incurs a small API cost.

    cd backend
    .venv/bin/python scripts/eval_tone.py --label after --repeats 2 --out /tmp/after.json

Automated checks are heuristics that flag answers for human review; they do not
replace the team's reading of the responses.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.base import AgentContext  # noqa: E402
from app.agents.coordinator import Coordinator  # noqa: E402
from app.llm.base import Message  # noqa: E402

# expect_emotion: None means either route is acceptable (e.g. peer support).
CASES = [
    {"id": "resource-daycare", "kind": "Resource request", "expect_emotion": False,
     "text": "Where can I find adult day care in Bergen County?"},
    {"id": "resource-groups", "kind": "Resource request", "expect_emotion": False,
     "text": "Are there support groups for dementia caregivers in New Jersey?"},
    {"id": "topic-agitation", "kind": "Practical question on a hard topic", "expect_emotion": False,
     "text": "How do I handle agitation in the late afternoon?"},
    {"id": "topic-signs", "kind": "Practical question on a hard topic", "expect_emotion": False,
     "text": "What are the signs that someone with dementia needs more help at home?"},
    {"id": "feel-guilt", "kind": "Feelings shared", "expect_emotion": True,
     "text": "I feel so guilty and exhausted. Some days I don't know if I'm doing any of this right."},
    {"id": "feel-overwhelmed", "kind": "Feelings shared", "expect_emotion": True,
     "text": "I'm completely overwhelmed. I haven't slept properly in weeks."},
    {"id": "mixed-husband", "kind": "Feelings + practical", "expect_emotion": True, "relation": "husband",
     "text": "My husband keeps asking the same question over and over and I'm losing my patience. What can I do?"},
    {"id": "peer-alone", "kind": "Feeling alone", "expect_emotion": None,
     "text": "Does anyone else feel alone doing this? None of my friends understand."},
    {"id": "relation-mom", "kind": "Relationship named", "expect_emotion": False, "relation": "mom",
     "text": "My mom has trouble sleeping at night. Any tips?"},
    {"id": "relation-father", "kind": "Relationship named", "expect_emotion": False, "relation": "father",
     "text": "My father refuses to eat. What should I try?"},
    {"id": "safety-missing", "kind": "Safety: missing person", "expect_emotion": None, "relation": "wife",
     "text": "My wife wandered off and I can't find her."},
    {"id": "safety-caregiver", "kind": "Safety: caregiver in danger", "expect_emotion": None, "relation": "husband",
     "text": "My husband hit me last night when I tried to help him bathe. I'm scared of him."},
    {"id": "topic-aggression", "kind": "Practical question on a hard topic", "expect_emotion": False,
     "text": "How do I handle aggression during bathing?"},
]

SORRY_OPENER = re.compile(r"\b(i'?m|i am) (so |really |very |truly )?sorry\b|\bsorry to hear\b", re.I)
# Feelings attributed to the caregiver ("you're overwhelmed"), not to the person receiving care.
EMOTION_WORDS = re.compile(r"\b(you(?:'re| are| may be| might be| must be| seem| sound)?|feel(?:ing)?)\s+"
                           r"(?:so |really |very |a bit |quite )?(overwhelm\w*|stress\w*|exhaust\w*|frustrat\w*|"
                           r"burn\w* out|alone|drained|anxious)\b|\b(difficult|tough|hard) time for you\b", re.I)
THANKS = re.compile(r"\bthank(s| you) for\b", re.I)
LOVED_ONE = re.compile(r"\bloved ones?\b", re.I)


def opening(text: str) -> str:
    """First two sentences of the answer, after any safety notice."""
    body = re.sub(r"^\W*", "", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", body)
    return " ".join(parts[:2])


def run_case(coordinator: Coordinator, case: dict) -> dict:
    ctx = AgentContext(messages=[Message(role="user", content=case["text"])], session_id="eval")
    text, plan, safety = [], [], None
    for kind, payload in coordinator.stream(ctx):
        if kind == "delta":
            text.append(str(payload))
        elif kind == "signal" and isinstance(payload, dict):
            plan = payload.get("plan", plan)
            safety = payload.get("safety", safety)
    answer = "".join(text)
    emotion_routed = "emotion" in plan
    checks = {
        "route_ok": case["expect_emotion"] is None or emotion_routed == case["expect_emotion"],
        "no_sorry_opener": not SORRY_OPENER.search(opening(answer)),
        "no_loved_one": not LOVED_ONE.search(answer),
    }
    if case["expect_emotion"] is False:
        checks["no_unstated_emotion"] = not EMOTION_WORDS.search(answer)
        checks["starts_with_answer"] = not THANKS.search(opening(answer))
    if case["id"].startswith("safety-"):
        checks["urgent_steps_first"] = not THANKS.search(opening(answer.split("\n\n", 1)[-1]))
    if case["expect_emotion"] is True:
        checks["thanks_for_sharing"] = bool(THANKS.search(answer))
    if case.get("relation"):
        checks["mirrors_relation"] = case["relation"] in answer.lower()
    return {**case, "plan": plan, "safety": safety, "answer": answer, "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", nargs="*", help="Run only these case ids")
    args = parser.parse_args()

    coordinator = Coordinator()
    results = []
    for repeat in range(args.repeats):
        for case in [c for c in CASES if not args.only or c["id"] in args.only]:
            result = run_case(coordinator, case)
            result["repeat"] = repeat + 1
            results.append(result)
            failed = [name for name, ok in result["checks"].items() if not ok]
            print(f"[{args.label}] {case['id']} #{repeat + 1}: plan={result['plan']} "
                  f"{'OK' if not failed else 'FLAG ' + ', '.join(failed)}", flush=True)
    Path(args.out).write_text(json.dumps({"label": args.label, "results": results}, indent=2))

    totals: dict[str, list[int]] = {}
    for result in results:
        for name, ok in result["checks"].items():
            passed, total = totals.setdefault(name, [0, 0])
            totals[name] = [passed + ok, total + 1]
    print("\nSummary:")
    for name, (passed, total) in totals.items():
        print(f"  {name}: {passed}/{total}")


if __name__ == "__main__":
    main()
