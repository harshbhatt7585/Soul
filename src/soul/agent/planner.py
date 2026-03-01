from __future__ import annotations

import re

from soul.agent.types import Plan, ToolCall
from soul.utils.text import looks_like_research_request
from souls.utils.touls import get_tools


class Planner:
    def build_plan(self, prompt: str, *, mode: str) -> Plan:
        normalized = re.sub(r"\s+", " ", prompt).strip()
        steps = [
            "Recall relevant memory for the request.",
            "Decide any tool needed for answring the request",
            f"You tools: {get_tools()}"
        ]
        tool_calls = [ToolCall(name="memory_recall", input={"query": normalized, "limit": 6})]

        if mode == "autonomous":
            steps.insert(0, "Interpret the request as a goal review and identify the next high-value action.")

        return Plan(objective=normalized, steps=steps, tool_calls=tool_calls)
