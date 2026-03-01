from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from soul.tools.base import ToolContext, ToolResult
from soul.tools.memory_read import MemoryReadTool
from soul.tools.memory_write import MemoryWriteTool
from soul.tools.web_fetch import WebFetchTool
from soul.tools.web_search import WebSearchTool


class Tools(ABC):
    description = ""

    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        return self(context, input_data)

    @abstractmethod
    def __call__(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        raise NotImplementedError


class MemoryRecallAgentTool(Tools):
    description = "Recall relevant memory entries for the current prompt."

    def __init__(self) -> None:
        super().__init__("memory_recall")
        self._tool = MemoryReadTool()

    def __call__(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        return self._tool.run(context, input_data)


class MemoryWriteAgentTool(Tools):
    description = "Write a note, preference, or outcome into local memory."

    def __init__(self) -> None:
        super().__init__("memory_write")
        self._tool = MemoryWriteTool()

    def __call__(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        return self._tool.run(context, input_data)


class WebSearchAgentTool(Tools):
    description = "Search the web with DuckDuckGo HTML results."

    def __init__(self) -> None:
        super().__init__("web_search")
        self._tool = WebSearchTool()

    def __call__(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        return self._tool.run(context, input_data)


class WebFetchAgentTool(Tools):
    description = "Fetch a web page and convert it into a readable excerpt."

    def __init__(self) -> None:
        super().__init__("web_fetch")
        self._tool = WebFetchTool()

    def __call__(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        return self._tool.run(context, input_data)


def build_default_tools() -> list[Tools]:
    return [
        MemoryRecallAgentTool(),
        MemoryWriteAgentTool(),
        WebSearchAgentTool(),
        WebFetchAgentTool(),
    ]


def get_tools() -> list[str]:
    return [f"{tool.name}: {tool.description}" for tool in build_default_tools()]


__all__ = [
    "Tools",
    "MemoryRecallAgentTool",
    "MemoryWriteAgentTool",
    "WebSearchAgentTool",
    "WebFetchAgentTool",
    "build_default_tools",
    "get_tools",
]
