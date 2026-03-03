from __future__ import annotations

import json
from typing import Any

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
    traces: list[dict[str, Any]] | list[object],
) -> str:
    soul_prompt = load_soul_prompt(config).strip() or DEFAULT_SOUL_PROMPT
    resolved_name = name.strip() or "Soul"
    tool_block = (
        "\n".join(
            f"- {getattr(trace, 'name', '')}: {getattr(trace, 'summary', '')}"
            if not isinstance(trace, dict)
            else f"- {trace.get('name', '')}: {trace.get('summary', '')}"
            for trace in traces
        )
        or "- none"
    )
    mode_instruction = (
        "Autonomous mode: propose the next highest-value action, one blocker, and one follow-up."
        if mode == "autonomous"
        else "Manual mode: respond directly to the user and keep the answer actionable."
    )

    return (
        f"{soul_prompt}\n\n"
        f"## Tool traces\n{tool_block}\n\n"
        f"You are a friendly personal assistant. Your name is {resolved_name}.\n"
        f"{mode_instruction}\n"
        "You run locally on a Python CLI stack. Be explicit about uncertainty and current tool coverage."
    )


def build_user_prompt(prompt: str, traces: list[dict[str, Any]] | list[object]) -> str:
    trace_block = (
        "\n\n".join(
            (
                f"Tool: {trace.get('name', '')}\nSummary: {trace.get('summary', '')}\nOutput:\n"
                f"{json.dumps(trace.get('output'), indent=2)}"
            )
            if isinstance(trace, dict)
            else (
                f"Tool: {getattr(trace, 'name', '')}\nSummary: {getattr(trace, 'summary', '')}\nOutput:\n"
                f"{json.dumps(getattr(trace, 'output', None), indent=2)}"
            )
            for trace in traces
        )
        if traces
        else "No tools were used for this turn."
    )
    return f"User request: {prompt}\n\n{trace_block}"


# TODO
def build_planning_prompt(prompt: str):
    return (
        ""
    )

# TODO
def tool_identification_prompt(prompt: str):
    return (
        ""
    )


# TODO
def build_inital_prompt(prompt: str):
    return (
        ""
    )
