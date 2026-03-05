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
    tools: list[str],
) -> str:
    return (
        "You are a personal assistant to help user to learn, study, understand and research."
        "You have given user context, use that to talk to user accordingly."
        "You have given tools to use to help answer user's request.",
        "GIVEN tools: {tools}",
    )




# TODO
def build_planning_prompt(prompt: str):
    return (
        "Think step by step and plan"
        "1. What is the user's request?"
        "2. What is the user's current context?"
        "3. Identify do we need any tools for the user's request? If yes, identify the best tool to use to answer user's request?"
        "4. Create a todo list to complete the user's request which inlcude steps to complete the user's request and the tool to use to complete the request."
        "5. Return the response in JSON format."
        
        f"""For example: 
        ```json
        {
            "plan": ...,
            "tools": [tool_name_1, tool_name_2, ...]
        }
        ```
        """
    )

# TODO
def tool_identification_prompt(prompt: str):
    return (
        ""
    )


# TODO
def build_respond_prompt(prompt: str):
    return (
        "Based on all the current context, respond to the user's request in a concise manner."
        f"User request: {prompt}"
        "Return the response in JSON format."
        f"""For example: 
        ```json
        {
            "text": ...,
        }
        ```
        """
        

    )