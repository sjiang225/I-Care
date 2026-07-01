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
                "🚨 If your loved one is missing, call **911** now — police can "
                "begin a search immediately, and time matters with dementia. "
                "Have a recent photo and description ready.\n\n"
            ),
        )

    return SafetyResult(triggered=False)
