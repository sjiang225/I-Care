"""log_wellbeing tool: records the caregiver's emotional state over time.

Powers the proposal's "track caregiver stress patterns and emotional well-being
over time" requirement. The Emotion-Support agent calls this when it detects
emotional content.
"""
from __future__ import annotations

from ..db import get_db
from ..llm.base import ToolSpec
from .base import Tool, registry

LOG_WELLBEING_SPEC = ToolSpec(
    name="log_wellbeing",
    description=(
        "Record the caregiver's current emotional state, inferred from the "
        "conversation. Call this whenever the caregiver expresses feelings, "
        "stress, or burden."
    ),
    parameters={
        "type": "object",
        "properties": {
            "stress_level": {
                "type": "integer",
                "description": "Overall stress/distress level, 1 (calm) to 5 (severe).",
                "minimum": 1,
                "maximum": 5,
            },
            "emotions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Emotions expressed, e.g. ['anxiety','guilt','grief'].",
            },
            "note": {
                "type": "string",
                "description": "A short summary of what the caregiver is going through.",
            },
        },
        "required": ["stress_level", "emotions"],
    },
)


def _handle(args: dict, session_id: str) -> dict:
    log = get_db().add_wellbeing(
        session_id=session_id,
        stress_level=args.get("stress_level", 3),
        emotions=args.get("emotions", []),
        note=args.get("note", ""),
    )
    return {
        "logged": True,
        "stress_level": log.stress_level,
        "emotions": log.emotions,
    }


registry.register(Tool(spec=LOG_WELLBEING_SPEC, handler=_handle))
