from __future__ import annotations

import json
from typing import Any

from soul.agent.prompts import build_planning_prompt, build_respond_prompt, build_system_prompt, verification_prompt
from soul.agent.scratchpad import ScratchpadStore
from soul.agent.tools import build_default_tools
from soul.agent.types import AgentEvent, RunResult
from soul.config import AgentConfig, model_for_mode
from soul.models.llm import LLMHandler, LLMProvider


def _extract_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


class Agent:
    def __init__(self, config: AgentConfig, llm_provider: LLMProvider | None = None) -> None:
        self._config = config
        self._scratchpad = ScratchpadStore(config)
        self._llm_handler = LLMHandler(config, provider=llm_provider)
        self._tools = {tool.name: tool for tool in build_default_tools(config)}
        self.context: list[dict[str, Any]] = []
        self.max_iter = 3

    def _call_llm(self, *, mode: str, model: str | None, prompt: str) -> dict[str, Any]:
        system_prompt = build_system_prompt(
            self._config,
            mode=mode,
            name="Soul",
            tools=[f"{name}: {tool.description}" for name, tool in self._tools.items()],
        )
        raw = self._llm_handler.generate(
            model=model_for_mode(self._config, mode, model),
            system=system_prompt,
            prompt=prompt,
        )
        return _extract_json(raw)

    def _run_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            name = str(tool_call.get("name", "")).strip()
            args = tool_call.get("args", {})
            if not isinstance(args, dict):
                args = {}

            tool = self._tools.get(name)
            if tool is None:
                results.append({"ok": False, "tool": name, "error": "unknown tool"})
                continue

            results.append(tool(args))
        return results

    def run(self, prompt: str, *, mode: str = "manual", model: str | None = None) -> RunResult:
        self.context.append({"role": "user", "content": prompt})
        events: list[AgentEvent] = []
        verification_feedback = ""

        for iteration in range(1, self.max_iter + 1):
            planning_input = prompt
            if verification_feedback:
                planning_input = f"{prompt}\nPrevious verification feedback: {verification_feedback}"

            plan = self._call_llm(
                mode=mode,
                model=model,
                prompt=build_planning_prompt(planning_input, self.context),
            )
            todo = plan.get("todo", [])
            plan_mode = str(plan.get("mode", "answer_directly"))
            tool_calls = plan.get("tool_calls", [])

            if not isinstance(todo, list):
                todo = []
            if not isinstance(tool_calls, list):
                tool_calls = []

            self.context.append(
                {
                    "role": "planner",
                    "content": {
                        "mode": plan_mode,
                        "todo": todo,
                        "tool_calls": tool_calls,
                        "notes": plan.get("notes", ""),
                    },
                }
            )
            events.append(
                AgentEvent(
                    kind="planning",
                    title=f"Iteration {iteration}",
                    detail=f"mode={plan_mode}; todo={json.dumps(todo, ensure_ascii=True)}",
                )
            )

            tool_results = self._run_tool_calls(tool_calls)
            if tool_results:
                self.context.append({"role": "tools", "content": tool_results})
                events.append(
                    AgentEvent(
                        kind="tool_execution",
                        title=f"Iteration {iteration}",
                        detail=json.dumps(tool_results, ensure_ascii=True),
                    )
                )

            verification = self._call_llm(
                mode=mode,
                model=model,
                prompt=verification_prompt(prompt, self.context),
            )
            ok = bool(verification.get("ok"))
            verification_feedback = str(verification.get("feedback", "")).strip()
            self.context.append({"role": "verifier", "content": verification})
            events.append(
                AgentEvent(
                    kind="verification",
                    title=f"Iteration {iteration}",
                    detail=json.dumps(verification, ensure_ascii=True),
                )
            )

            response = self._call_llm(
                mode=mode,
                model=model,
                prompt=build_respond_prompt(prompt, self.context),
            )
            reply = str(response.get("text", "")).strip()
            if reply:
                self.context.append({"role": "assistant", "content": reply})

            if ok or iteration == self.max_iter:
                return RunResult(
                    reply=reply or "I could not produce a final response.",
                    events=events,
                    iterations=iteration,
                    meta={"plan_mode": plan_mode, "todo": todo},
                )

        return RunResult(reply="I could not complete the request.", events=events, iterations=self.max_iter)

    def reset(self) -> None:
        self._scratchpad.reset()
        self.context = []


SoulAgent = Agent


__all__ = ["Agent", "SoulAgent"]
