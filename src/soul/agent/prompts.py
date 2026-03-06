from __future__ import annotations

import json
from typing import Any

from soul.agent.tools import get_tools
from soul.config import AgentConfig

DEFAULT_SOUL_PROMPT = """# Soul

Soul is a local-first personal CLI assistant.

- Be concise.
- Use tools when useful.
- Do not claim actions happened unless tool output supports it.
"""


def load_soul_prompt(config: AgentConfig) -> str:
    try:
        return config.soul_path.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_SOUL_PROMPT


def build_system_prompt(
    config: AgentConfig,
    *,
    name: str,
    tools: list[str] | None = None,
) -> str:
    tool_list = tools or get_tools()
    soul_prompt = load_soul_prompt(config)
    return "\n".join(
        [
            soul_prompt.strip(),
            "",
            f"Assistant name: {name}",
            "Available tools:",
            *[f"- {tool}" for tool in tool_list],
            "",
            "Return valid JSON when the user prompt asks for structured output.",
        ]
    )


def _json_block(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2)


def build_planning_prompt(prompt: str, context: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "Plan the next agent step.",
            f"User request: {prompt}",
            f"Context so far: {json.dumps(context, ensure_ascii=True)}",
            "Think step by step before answering.",
            "Reason through the request, the available context, and whether tools are needed.",
            "Return JSON only.",
            "The plan should be simple and actionable.",
            _json_block(
                {
                    "todo": ["step 1", "step 2"],
                    "tool_calls": [
                        {"name": "web_search", "args": {"query": "....", "topic": "...."}},
                        {"name": "web_fetch", "args": {"url": "....."}}
                    ],
                    "reasoning": "step-by-step planning rationale",
                    "notes": "short planning note",
                }
            ),
        ]
    )


def verification_prompt(prompt: str, context: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "Verify whether the current context is sufficient to answer the user.",
            f"User request: {prompt}",
            f"Context so far: {json.dumps(context, ensure_ascii=True)}",
            "Think step by step before answering.",
            "Explain to yourself whether the answer fully satisfies the user and what is still missing if not.",
            "Return JSON only.",
            _json_block(
                {
                    "ok": True,
                    "reasoning": "step-by-step verification rationale",
                    "feedback": "empty if complete, otherwise explain what is missing",
                }
            ),
        ]
    )


def build_respond_prompt(prompt: str, context: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "Write the final response to the user using the available context.",
            f"User request: {prompt}",
            f"Context so far: {json.dumps(context, ensure_ascii=True)}",
            "Think step by step before answering.",
            "Use the reasoning to produce the best concise final response.",
            "Return JSON only.",
            _json_block(
                {
                    "reasoning": "step-by-step response rationale",
                    "text": "final assistant response",
                }
            ),
        ]
    )
