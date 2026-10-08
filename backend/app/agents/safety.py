"""Safety guardrail: a fast, rule-based pre-check for crisis / emergency content.

Runs before the LLM on every turn. If it fires, the Coordinator surfaces an
urgent, actionable notice ahead of the normal answer. Deliberately conservative
(a gentle extra "call 911" is acceptable; a missed emergency is not).

This is a deterministic first line of defense; an LLM-based classifier can be
layered on later for nuance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SafetyResult:
    triggered: bool
    category: str | None = None
    message: str | None = None


_SELF_HARM = [
    "kill myself", "suicide", "suicidal", "end my life", "want to die",
    "don't want to live", "hurt myself", "harm myself",
]
_MEDICAL = [
    "chest pain", "can't breathe", "cannot breathe", "not breathing",
    "unconscious", "unresponsive", "passed out", "seizure", "stroke",
    "choking", "severe bleeding", "bleeding badly", "overdose", "won't wake up",
    "can't wake", "blue lips", "turning blue",
]
_MISSING = [
    "wandered off", "can't find him", "can't find her", "cannot find him",
    "cannot find her", "she is missing", "he is missing", "got lost",
    "ran away", "left the house and",
]

# R09: the caregiver (or the person they support) is at risk of harm -- e.g.
# aggression from the person living with dementia. Phrases are specific on
# purpose: "it hurt me when she forgot my name" must not trigger.
_CAREGIVER_DANGER = [
    "hit me", "hits me", "hitting me", "punched me", "kicked me", "choked me",
    "attacked me", "attacks me", "slapped me", "bit me", "shoved me",
    "threatened me", "threatens me", "threatening me", "threatened to kill",
    "has a knife", "has a gun", "afraid of him", "afraid of her",
    "scared of him", "scared of her", "i'm not safe", "i am not safe",
    "don't feel safe", "do not feel safe", "fear for my safety",
    "afraid for my safety", "fear for his safety", "fear for her safety",
    "i'm in danger", "i am in danger", "he's in danger", "she's in danger",
    "we're in danger", "we are in danger",
]

_HELPLINE = "Care2Caregivers helpline: 1-800-424-2494"


def _matches(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def check_safety(text: str) -> SafetyResult:
    t = re.sub(r"\s+", " ", text.lower())

    if _matches(t, _SELF_HARM):
        return SafetyResult(
            triggered=True,
            category="self_harm",
            message=(
                "💛 It sounds like you may be in serious distress. You are not "
                "alone. Please reach out right now: call or text **988** (Suicide "
                "& Crisis Lifeline, 24/7). If you are in immediate danger, call "
                "**911**.\n\n"
            ),
        )

    if _matches(t, _MEDICAL):
        return SafetyResult(
            triggered=True,
            category="medical_emergency",
            message=(
                "🚨 This may be a medical emergency. Please call **911** right "
                "away. I can offer general support, but I am not a substitute for "
                "emergency care.\n\n"
            ),
        )

    if _matches(t, _MISSING):
        return SafetyResult(
            triggered=True,
            category="missing_person",
            message=(
                "🚨 If the person you care for is missing, call **911** now — police can "
                "begin a search immediately, and time matters with dementia. "
                "Have a recent photo and description ready.\n\n"
            ),
        )

    if _matches(t, _CAREGIVER_DANGER):
        return SafetyResult(
            triggered=True,
            category="caregiver_safety",
            message=(
                "🚨 If you ever feel in danger or fear for the safety of the person "
                "you are supporting, call **911**. Emergency workers can assist you "
                "and help you in a crisis.\n\n"
            ),
        )

    return SafetyResult(triggered=False)
