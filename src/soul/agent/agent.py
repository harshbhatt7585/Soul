from __future__ import annotations

import json
from typing import Any, Callable

from soul.agent.prompts import (
    build_planning_prompt,
    build_respond_prompt,
    build_system_prompt,
    build_tool_identification_prompt,
    build_tool_calling_prompt,
    verification_prompt,
)
from soul.agent.tools import build_default_tools, build_ollama_tools
from soul.agent.types import RunResult
from soul.config import AgentConfig, model_for_mode
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
        self.context: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': build_system_prompt(config, name="Soul"),
            }
        ]
        self.max_iter = 3

    def _call_llm_json(
        self,
        *,
        model: str | None,
        prompt: str,
        extra_messages: list[ChatMessage] | None = None,
    ) -> dict[str, Any]:
        response = self._chat(model=model, prompt=prompt, extra_messages=extra_messages, format="json")
        return _extract_json(response.content)

    def _chat(
        self,
        *,
        model: str | None,
        prompt: str,
        extra_messages: list[ChatMessage] | None = None,
        format: str | None = None,
        stream: bool = False,
        on_chunk: Callable[[str], None] | None = None,
        on_reasoning_chunk: Callable[[str], None] | None = None,
    ) -> ChatResponse:
        messages = list(self.context)
        if extra_messages:
            messages.extend(extra_messages)
        messages.append({"role": "user", "content": prompt})
        return self._llm_handler.chat(
            messages=messages,
            model=model_for_mode(self._config, "default", override=model),
            format=format,
            stream=stream,
            on_chunk=on_chunk,
            on_reasoning_chunk=on_reasoning_chunk,
        )

    def run(
        self,
        prompt: str,
        *,
        model: str | None = None,
        stream: bool = False,
        on_chunk: Callable[[str], None] | None = None,
        on_reasoning_chunk: Callable[[str], None] | None = None,
    ) -> RunResult:
        plan_prompt = build_planning_prompt(prompt=prompt)
        response = self._chat(
            model=model,
            prompt=plan_prompt,
            format="json",
            stream=stream,
            on_chunk=on_chunk,
            on_reasoning_chunk=on_reasoning_chunk,
        )

        tool_calls = json.loads(response.content)['tool_calls']
        print("\n", tool_calls)

        tool_calling_prompt = build_tool_calling_prompt(prompt=prompt, tools_calls=tool_calls)

        response = self._chat(
            model=model,
            prompt=tool_calling_prompt,
            format="json",
            stream=stream,
            on_chunk=on_chunk,
            on_reasoning_chunk=on_reasoning_chunk,

        )



        

        return RunResult(
            reply=response.content,
            iterations=1,
            meta={
                "reasoning": response.reasoning,
                "tool_calls": response.tool_calls,
            },
        )


    def reset(self) -> None:
        self.context = [
            {
                "role": "system",
                "content": build_system_prompt(self._config, name="Soul"),
            }
        ]


SoulAgent = Agent


__all__ = ["Agent", "SoulAgent"]
