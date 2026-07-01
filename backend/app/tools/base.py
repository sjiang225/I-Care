"""Tool registry + dispatch for agent tool-calling.

A Tool bundles an LLM-facing ToolSpec with a server-side handler. Agents pass
specs to the model; when the model calls one, the registry dispatches it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..llm.base import ToolCall, ToolSpec

# Handler receives the parsed arguments + the session id; returns a JSON-able dict.
ToolHandler = Callable[[dict, str], dict]


@dataclass
class Tool:
    spec: ToolSpec
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.spec.name] = tool

    def specs(self, names: list[str] | None = None) -> list[ToolSpec]:
        items = self._tools.values()
        if names is not None:
            items = [self._tools[n] for n in names if n in self._tools]
        return [t.spec for t in items]

    def dispatch(self, call: ToolCall, session_id: str) -> dict:
        tool = self._tools.get(call.name)
        if tool is None:
            return {"error": f"unknown tool: {call.name}"}
        return tool.handler(call.arguments, session_id)


# Process-wide registry populated by tool modules (see wellbeing.py).
registry = ToolRegistry()
