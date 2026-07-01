"""Caregiver-state assessment: turn the well-being trend into gentle guidance.

Threshold-gated so the system only shifts to a more supportive posture when
stress is genuinely high/rising. Design principles (keep them):
  * Restraint  -- trigger only past the threshold; never nag every turn.
  * No surveillance feel -- never quote the logs or say "last time you said…".
  * Support, not judgment -- the goal is to lighten the load and point to help.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..db import WellbeingSummary

# A gentle instruction handed to agents (NOT shown verbatim to the caregiver).
_HIGH_STRESS_NOTE = (
    "Context: this caregiver has been under high stress lately. Open with one "
    "brief, warm sentence acknowledging how hard things have been — WITHOUT "
    "quoting specifics or mentioning that their mood is tracked — then help, and "
    "gently remind them that support is available for them too."
)


@dataclass
class CaregiverState:
    high_stress: bool
    note: str | None = None


def assess_caregiver_state(summary: WellbeingSummary) -> CaregiverState:
    """Decide whether to adopt a more supportive posture this turn."""
    if summary.count < 3:  # not enough history to judge
        return CaregiverState(False)

    high = summary.avg_stress >= 3.5 or (
        summary.latest_stress is not None
        and summary.latest_stress >= 4
        and summary.trend == "up"
    )
    return CaregiverState(True, _HIGH_STRESS_NOTE) if high else CaregiverState(False)
