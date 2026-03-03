from __future__ import annotations

from soul.agent.scratchpad import ScratchpadStore
from soul.agent.types import AgentEvent, RunResult
from soul.config import AgentConfig
from soul.models.llm import LLMHandler

DEFAULT_SOUL_MD = """# Soul

Soul is a personal open-source CLI assistant that runs locally first.

## Identity

- Be pragmatic, concise, and explicit.
- Work with the user's current goal and available tools.
- Do not pretend work happened if no tool or model output supports it.
"""


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
        self._config.soul_path.parent.mkdir(parents=True, exist_ok=True)
        if force_identity or not self._config.soul_path.exists():
            self._config.soul_path.write_text(DEFAULT_SOUL_MD + "\n", encoding="utf-8")
            soul_created = True
        else:
            soul_created = False
        return {
            "workspace_root": str(self._config.workspace_root),
            "soul_home": str(self._config.soul_home),
            "scratchpad_path": str(self._config.scratchpad_path),
            "soul_path": str(self._config.soul_path),
            "soul_created": soul_created,
        }


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
