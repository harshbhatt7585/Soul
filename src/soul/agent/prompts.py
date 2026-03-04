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

# TODO: implement build_system_prompt function.
def build_system_prompt(
    config: AgentConfig,
    *,
    mode: str,
    name: str,
    traces: list[dict[str, Any]] | list[object],
) -> str:
    pass




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
