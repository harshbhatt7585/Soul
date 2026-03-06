from __future__ import annotations

import json
from typing import Any

from soul.agent.prompts import (
    build_planning_prompt,
    build_respond_prompt,
    build_system_prompt,
    build_tool_identification_prompt,
    verification_prompt,
)
from soul.agent.scratchpad import ScratchpadStore
from soul.agent.tools import build_default_tools
from soul.agent.types import AgentEvent, RunResult
from soul.config import AgentConfig
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

    def _call_llm(self, *, model: str | None, prompt: str) -> dict[str, Any]:
        system_prompt = build_system_prompt(
            self._config,
            name="Soul",
            tools=[f"{name}: {tool.description}" for name, tool in self._tools.items()],
        )
        raw = self._llm_handler.generate(
            model=model or self._config.manual_model,
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

    def run(self, prompt: str, *, model: str | None = None) -> RunResult:
        self.context.append({"role": "user", "content": prompt})
        events: list[AgentEvent] = []

        for iteration in range(1, self.max_iter + 1):
            plan = self._call_llm(
                model=model,
                prompt=build_planning_prompt(prompt, self.context),
            )
            print("Plan", plan)
            todo = plan.get("todo", [])
            plan_reasoning = str(plan.get("reasoning", "")).strip()

            if not isinstance(todo, list):
                todo = []

            self.context.append(
                {
                    "role": "planner",
                    "content": {
                        "todo": todo,
                        "reasoning": plan_reasoning,
                        "notes": plan.get("notes", ""),
                    },
                }
            )
            events.append(
                AgentEvent(
                    kind="planning",
                    title=f"Iteration {iteration}",
                    detail=f"todo={json.dumps(todo, ensure_ascii=True)}",
                )
            )

            tool_identification = self._call_llm(
                model=model,
                prompt=build_tool_identification_prompt(prompt, self.context),
            )
            tool_calls = tool_identification.get("tool_calls", [])
            tool_reasoning = str(tool_identification.get("reasoning", "")).strip()
            if not isinstance(tool_calls, list):
                tool_calls = []

            self.context.append(
                {
                    "role": "tool_identification",
                    "content": {
                        "tool_calls": tool_calls,
                        "reasoning": tool_reasoning,
                        "notes": tool_identification.get("notes", ""),
                    },
                }
            )
            events.append(
                AgentEvent(
                    kind="tool_identification",
                    title=f"Iteration {iteration}",
                    detail=json.dumps(tool_calls, ensure_ascii=True),
                )
            )

            tool_results = self._run_tool_calls(tool_calls)

            print(tool_results)

            if tool_results:
                self.context.append({"role": "tools", "content": tool_results})
                events.append(
                    AgentEvent(
                        kind="tool_execution",
                        title=f"Iteration {iteration}",
                        detail=json.dumps(tool_results, ensure_ascii=True),
                    )
                )

            response = self._call_llm(
                model=model,
                prompt=build_respond_prompt(prompt, self.context),
            )
            reply = str(response.get("text", "")).strip()
            response_reasoning = str(response.get("reasoning", "")).strip()
            if reply:
                self.context.append(
                    {
                        "role": "assistant",
                        "content": {
                            "text": reply,
                            "reasoning": response_reasoning,
                        },
                    }
                )

            verification = self._call_llm(
                model=model,
                prompt=verification_prompt(prompt, self.context, candidate_answer=reply),
            )
            ok = bool(verification.get("ok"))
            self.context.append({"role": "verifier", "content": verification})
            events.append(
                AgentEvent(
                    kind="verification",
                    title=f"Iteration {iteration}",
                    detail=json.dumps(verification, ensure_ascii=True),
                )
            )

            if ok or iteration == self.max_iter:
                return RunResult(
                    reply=reply or "I could not produce a final response.",
                    events=events,
                    iterations=iteration,
                    meta={"todo": todo},
                )

        return RunResult(reply="I could not complete the request.", events=events, iterations=self.max_iter)

    def reset(self) -> None:
        self._scratchpad.reset()
        self.context = []


SoulAgent = Agent


__all__ = ["Agent", "SoulAgent"]
