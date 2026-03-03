from __future__ import annotations

import json
import re
from soul.agent.scratchpad import ScratchpadStore
from soul.agent.types import AgentEvent, RunResult
from soul.config import AgentConfig
from soul.models.llm import LLMHandler


# TODO: implement SoulAgent.
class SoulAgent:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._scratchpad = ScratchpadStore(config)
        self._llm_handler = LLMHandler(config)


    def _available_tools(self) -> list[str]:
        return [f"{tool.name}: {tool.description}" for tool in self._registry.list()]


    def initialize_state(self, *, force_identity: bool = False) -> dict[str, object]:
        self._scratchpad.ensure_ready()


    def run(self, prompt: str, *, mode: str = "manual", model: str | None = None) -> RunResult:
        normalized = prompt.strip()
        if not normalized:
            raise ValueError("Prompt must not be empty.")

        self.initialize_state()
        planning_event = AgentEvent(
            kind="planning",
            title="Reasoning",
            detail=" | ".join(plan.steps),
        )
        self._scratchpad.append(planning_event)

        result = self._exectue_plan(prompt)
        result = self._execute_action(result)
        result = self._respond(result)

        result_event = AgentEvent(kind="result", title="Reply", detail=truncate(reply, 200))
        self._scratchpad.append(result_event)

        return RunResult(
            prompt=prompt,
            reply=result,
        )
