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

    def run(self, prompt):
        plan_prompt = build_planning_prompt(messages=self.context)
        self.context.append({
            'role': 'assistant',
            'content': plan_prompt
        })
        print(self._llm_handler.chat(
            messages=plan_prompt,
            model=self._config.model
        ))


    def reset(self) -> None:
        self.context = []


SoulAgent = Agent


__all__ = ["Agent", "SoulAgent"]
