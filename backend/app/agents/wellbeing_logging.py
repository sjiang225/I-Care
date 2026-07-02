"""Shared well-being logging: one forced tool call -> logged mood signal.

Used by the Emotion-Support and Peer-Support agents (both are emotional
contexts). Keeps the log_wellbeing behavior in one place.
"""
from __future__ import annotations

from ..llm.base import Message
from ..llm.factory import get_llm
from ..tools import wellbeing as _wb  # noqa: F401  (registers the tool)
from ..tools.base import registry
from ..tools.wellbeing import LOG_WELLBEING_SPEC
from .base import AgentContext


def assess_and_log_wellbeing(ctx: AgentContext, history_turns: int = 6) -> dict | None:
    """Assess the caregiver's state and record it via the log_wellbeing tool.
    Best-effort: never blocks the reply if it fails."""
    try:
        result = get_llm().chat(
            [
                Message(
                    role="system",
                    content=(
                        "Assess the caregiver's emotional state from the "
                        "conversation and record it by calling log_wellbeing."
                    ),
                ),
                *ctx.recent(history_turns),
            ],
            tools=[LOG_WELLBEING_SPEC],
            tool_choice={"type": "function", "function": {"name": "log_wellbeing"}},
            temperature=0,
        )
        if result.tool_calls:
            return registry.dispatch(result.tool_calls[0], ctx.session_id)
    except Exception:
        return None
    return None
