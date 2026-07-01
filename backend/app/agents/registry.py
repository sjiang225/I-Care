"""AgentRegistry: agents as named, composable units.

The Coordinator registers specialist agents here and looks them up by name when
executing a Plan. This is the "agents as composable tools" realization -- adding
a future agent is just register() + a Plan rule.
"""
from __future__ import annotations

from .base import Agent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        if name not in self._agents:
            raise KeyError(f"unknown agent: {name}")
        return self._agents[name]

    def names(self) -> list[str]:
        return list(self._agents)
