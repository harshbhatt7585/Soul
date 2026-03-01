from __future__ import annotations

import re

from soul.agent.types import Plan, ToolCall
from soul.utils.text import looks_like_research_request


class Planner:
    def build_plan(self, prompt: str, *, mode: str) -> Plan:
        normalized = re.sub(r"\s+", " ", prompt).strip()
        steps = [
            "Recall relevant memory for the request.",
            "Decide any tool needed for answring the request",
        ]
        tool_calls = [ToolCall(name="memory_recall", input={"query": normalized, "limit": 6})]

        remember_match = re.match(r"^remember(?::|\s+)(.+)$", normalized, flags=re.IGNORECASE)
        if remember_match:
            tool_calls.append(
                ToolCall(
                    name="memory_write",
                    input={"content": remember_match.group(1).strip(), "kind": "note", "tags": [mode]},
                )
            )

        if looks_like_research_request(normalized):
            steps.insert(2, "Use web search and page fetch tools to gather source material.")
            tool_calls.append(ToolCall(name="web_search", input={"query": normalized}))

        if mode == "autonomous":
            steps.insert(0, "Interpret the request as a goal review and identify the next high-value action.")

        return Plan(objective=normalized, steps=steps, tool_calls=tool_calls)
