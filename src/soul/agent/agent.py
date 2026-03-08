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
from soul.agent.tools import build_default_tools, build_ollama_tools
from soul.agent.types import RunResult
from soul.config import AgentConfig
from soul.models.llm import ChatMessage, ChatResponse, LLMHandler, LLMProvider
from soul.utils import is_valid_plan, is_valid_response, is_valid_verification


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
        self._llm_handler = LLMHandler(config, provider=llm_provider)
        tool_list = build_default_tools(config)
        self._tools = {tool.name: tool for tool in tool_list}
        self._ollama_tools = build_ollama_tools(tool_list)
        self.context: list[dict[str, Any]] = []
        self.max_iter = 3

    def _conversation_to_messages(self, system_prompt: str, prompt: str) -> list[ChatMessage]:
        messages: list[ChatMessage] = [{"role": "system", "content": system_prompt}]
        for entry in self.context:
            role = str(entry.get("role", "")).strip().lower()
            content = entry.get("content", "")
            if role not in {"user", "assistant"}:
                continue
            messages.append({"role": role, "content": str(content)})

        messages.append({"role": "user", "content": prompt})
        return messages

    def _chat(
        self,
        *,
        model: str | None,
        prompt: str,
        tools: list[dict[str, Any]] | None = None,
        extra_messages: list[ChatMessage] | None = None,
        format: str | None = None,
    ) -> ChatResponse:
        system_prompt = build_system_prompt(
            self._config,
            name="Soul",
            tools=[f"{name}: {tool.description}" for name, tool in self._tools.items()],
        )
        messages = self._conversation_to_messages(system_prompt, prompt)
        if extra_messages:
            messages[-1:-1] = extra_messages
        return self._llm_handler.chat(
            model=model or self._config.manual_model,
            messages=messages,
            tools=tools,
            format=format,
        )

    def _call_llm_json(
        self,
        *,
        model: str | None,
        prompt: str,
        extra_messages: list[ChatMessage] | None = None,
    ) -> dict[str, Any]:
        response = self._chat(model=model, prompt=prompt, extra_messages=extra_messages, format="json")
        return _extract_json(response.content)

    def _normalize_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(tool_call, dict):
            return {}
        function_payload = tool_call.get("function", {})
        if not isinstance(function_payload, dict):
            function_payload = {}
        name = str(function_payload.get("name", tool_call.get("name", ""))).strip()
        raw_args = function_payload.get("arguments", tool_call.get("args", {}))
        args: dict[str, Any]
        if isinstance(raw_args, dict):
            args = raw_args
        elif isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            else:
                args = parsed if isinstance(parsed, dict) else {}
        else:
            args = {}
        return {"name": name, "args": args}

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

        for iteration in range(1, self.max_iter + 1):
            plan = self._call_llm_json(
                model=model,
                prompt=build_planning_prompt(messages=self.context),
            )
            print("Plan", plan)
            if not is_valid_plan(plan):
                self.context.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "planner_error": "invalid plan payload",
                                "payload": plan,
                            },
                            ensure_ascii=True,
                        ),
                    }
                )
                continue
            plan_text = json.dumps(plan, ensure_ascii=True)
            self.context.append({"role": "assistant", "content": plan_text})
            todo = plan.get("todo", [])
            if not isinstance(todo, list):
                todo = []

            tool_identification = self._chat(
                model=model,
                prompt=build_tool_identification_prompt(messages=self.context),
                tools=self._ollama_tools,
            )
            tool_calls = [self._normalize_tool_call(tool_call) for tool_call in tool_identification.tool_calls]
            tool_calls = [tool_call for tool_call in tool_calls if tool_call.get("name")]
            tool_identification_text = tool_identification.content.strip() or json.dumps(
                {"tool_calls": tool_calls},
                ensure_ascii=True,
            )
            print("TOOL IDENTIFUCATION:", tool_identification_text)
            self.context.append({"role": "assistant", "content": tool_identification_text})

            tool_results = self._run_tool_calls(tool_calls)
            print("tool results", tool_results)
            tool_messages: list[ChatMessage] = []
            if tool_identification.tool_calls:
                tool_messages.append(
                    {
                        "role": "assistant",
                        "content": tool_identification.content,
                        "tool_calls": tool_identification.tool_calls,
                    }
                )

            if tool_results:
                for tool_call, result in zip(tool_calls, tool_results, strict=False):
                    tool_messages.append(
                        {
                            "role": "tool",
                            "name": str(tool_call.get("name", "")),
                            "content": json.dumps(result, ensure_ascii=True),
                        }
                    )

            response = self._call_llm_json(
                model=model,
                prompt=build_respond_prompt(messages=self.context),
                extra_messages=tool_messages,
            )
            print("RESPONSE:", response)
            if not is_valid_response(response):
                self.context.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "response_error": "invalid response payload",
                                "payload": response,
                            },
                            ensure_ascii=True,
                        ),
                    }
                )
                continue
            reply = str(response.get("text", "")).strip()
            response_reasoning = str(response.get("reasoning", "")).strip()
            if reply:
                self.context.append({"role": "assistant", "content": reply})
            del response_reasoning

            verification_messages = list(self.context)
            verification_messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps({"candidate_answer": reply}, ensure_ascii=True),
                }
            )
            verification = self._call_llm_json(
                model=model,
                prompt=verification_prompt(messages=verification_messages),
                extra_messages=tool_messages,
            )
            print("VERIFICATION: ", verification)
            if not is_valid_verification(verification):
                self.context.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "verification_error": "invalid verification payload",
                                "payload": verification,
                            },
                            ensure_ascii=True,
                        ),
                    }
                )
                continue
            self.context.append({"role": "assistant", "content": json.dumps(verification, ensure_ascii=True)})
            verification_feedback = str(verification.get("feedback", "")).strip()
            ok = bool(verification.get("ok")) and not verification_feedback

            if ok or iteration == self.max_iter:
                return RunResult(
                    reply=reply or "I could not produce a final response.",
                    iterations=iteration,
                    meta={"todo": todo},
                )

        return RunResult(reply="I could not complete the request.", iterations=self.max_iter)

    def reset(self) -> None:
        self.context = []


SoulAgent = Agent


__all__ = ["Agent", "SoulAgent"]
