from __future__ import annotations

import json

from soul.agent.types import ToolTrace
from soul.config import Settings
from soul.storage.memory import MemoryEntry

DEFAULT_PROFILE = """# Soul

Soul is a local-first personal CLI assistant.

- Be concise.
- Use tools and memory when useful.
- Do not claim actions happened unless tool output supports it.
"""


def load_profile(settings: Settings) -> str:
    try:
        return settings.profile_path.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_PROFILE


def load_identity(settings: Settings) -> dict[str, object]:
    try:
        return json.loads(settings.identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_system_prompt(
    settings: Settings,
    *,
    mode: str,
    name: str,
    memories: list[MemoryEntry],
    traces: list[ToolTrace],
    validation_reasons: list[str],
) -> str:
    identity = load_identity(settings)
    resolved_name = name.strip() or str(identity.get("name", "Soul")).strip() or "Soul"
    memory_block = "\n".join(f"- [{memory.kind}] {memory.content}" for memory in memories) or "- none"
    tool_block = "\n".join(f"- {trace.name}: {trace.summary}" for trace in traces) or "- none"
    validation_block = "\n".join(f"- {reason}" for reason in validation_reasons) or "- none"
    mode_instruction = (
        "Autonomous mode: propose the next highest-value action, one blocker, and one follow-up."
        if mode == "autonomous"
        else "Manual mode: respond directly to the user and keep the answer actionable."
    )

    return (
        f"{load_profile(settings)}\n\n"
        f"## Identity\n{json.dumps(identity, indent=2)}\n\n"
        f"## Relevant memory\n{memory_block}\n\n"
        f"## Tool traces\n{tool_block}\n\n"
        f"## Validation notes\n{validation_block}\n\n"
        f"You are a friendly personal assistant. Your name is {resolved_name}.\n"
        f"{mode_instruction}\n"
        "You run locally on a Python CLI stack. Be explicit about uncertainty and current tool coverage."
    )


def build_user_prompt(prompt: str, traces: list[ToolTrace]) -> str:
    trace_block = (
        "\n\n".join(
            f"Tool: {trace.name}\nSummary: {trace.summary}\nOutput:\n{json.dumps(trace.output, indent=2)}"
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
