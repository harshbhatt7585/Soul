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
- Use memory tools for durable preferences, stable facts, and ongoing project context.
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
            "Memory guidance:",
            "- Use memory_recall when the request may depend on prior preferences, project context, or saved facts.",
            "- Use memory_write when the user asks to remember something or states a stable preference or long-term fact that will matter later.",
            "- Do not write trivial one-off details or temporary information to memory.",
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
            "Pay attention to previous plan reasoning, tool outcomes, drafted answers, and verifier feedback.",
            "If the user message is a simple acknowledgement, greeting, or sign-off, return no tool calls.",
            "If the request may depend on saved preferences or past facts, call memory_recall before other tools.",
            "If the user shares a stable preference, long-term goal, identity detail, or explicitly asks you to remember something, include memory_write.",
            "Return JSON only.",
            "The plan should be simple and actionable.",
            _json_block(
                {
                    "todo": ["recall memory if needed", "use external tools only if needed", "write memory only if warranted"],
                    "reasoning": "step-by-step planning rationale",
                    "notes": "short planning note",
                }
            ),
        ]
    )


def build_tool_identification_prompt(prompt: str, context: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "Identify which tools, if any, should be called next.",
            f"User request: {prompt}",
            f"Context so far: {json.dumps(context, ensure_ascii=True)}",
            "Think step by step before answering.",
            "Use the planner output, previous tool results, drafted answers, and verifier feedback to decide whether another tool call is needed.",
            "If the user message is a simple acknowledgement, greeting, or sign-off, return no tool calls.",
            "If the request may depend on saved preferences or past facts and memory has not been checked, call memory_recall before other tools.",
            "Do not call web_search for generic chit-chat, acknowledgements, or when the answer is already available from context.",
            "If a tool previously failed and retrying without new information will not help, return no tool calls.",
            "Return JSON only.",
            _json_block(
                {
                    "tool_calls": [
                        {"name": "memory_recall", "args": {"query": "<query>", "limit": 3}},
                        {"name": "web_search", "args": {"query": "<query>", "topic": "<general_or_news>"}},
                        {"name": "memory_write", "args": {"text": "<text>", "kind": "<kind>", "tags": ["<tag>"]}},
                    ],
                    "reasoning": "step-by-step tool selection rationale",
                    "notes": "short tool selection note",
                }
            ),
        ]
    )


def verification_prompt(prompt: str, context: list[dict[str, Any]], *, candidate_answer: str = "") -> str:
    answer = candidate_answer.strip()
    return "\n".join(
        [
            "Verify whether the current context is sufficient to answer the user.",
            f"User request: {prompt}",
            f"Context so far: {json.dumps(context, ensure_ascii=True)}",
            *([f"Candidate answer: {answer}"] if answer else []),
            "Think step by step before answering.",
            "Explain to yourself whether the answer fully satisfies the user and what is still missing if not.",
            "If the answer may depend on saved preferences or prior facts and memory was not checked, treat that as potentially incomplete.",
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
            "Address any verifier feedback that is still relevant.",
            "If memory results were returned, use only the relevant confirmed memories.",
            "Return JSON only.",
            _json_block(
                {
                    "reasoning": "step-by-step response rationale",
                    "text": "final assistant response",
                }
            ),
        ]
    )
