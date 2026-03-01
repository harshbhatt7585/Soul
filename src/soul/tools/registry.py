from __future__ import annotations

from typing import Any

from soul.tools.base import Tool, ToolContext, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def run(self, name: str, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        return self.get(name).run(context, input_data)
