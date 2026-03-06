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
    mode: str,
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
            f"Operating mode: {mode}",
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
            "Return JSON only.",
            "The plan should be simple and actionable.",
            _json_block(
                {
                    "mode": "answer_directly_or_use_tools",
                    "todo": ["step 1", "step 2"],
                    "tool_calls": [
                        {"name": "web_fetch", "args": {"url": "https://example.com"}}
                    ],
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
            "Return JSON only.",
            _json_block(
                {
                    "ok": True,
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
            "Return JSON only.",
            _json_block({"text": "final assistant response"}),
        ]
    )
