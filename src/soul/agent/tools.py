from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


# TODO: implement Tool abstracted.
class Tools(ABC):
    description = ""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def __call__(self) -> None:
        raise NotImplementedError

# TODO: Consider adding more features or extending behavior for MemoryRecallAgentTool.
class MemoryRecallAgentTool(Tools):
    description = "Recall relevant memory entries for the current prompt."

    def __init__(self) -> None:
        # TODO: Accept configuration options for future memory providers.
        super().__init__("memory_recall")

    def __call__(self) -> None:
        # TODO: Consider filtering results or providing ranking based on relevance.
        pass

# TODO: Consider logging or auditing memory write actions.
class MemoryWriteAgentTool(Tools):
    description = "Write a note, preference, or outcome into local memory."

    def __init__(self) -> None:
        # TODO: Check for duplicate memory entries before writing.
        super().__init__("memory_write")

    def __call__(self) -> None:
        # TODO: Validate input_data format before writing to memory.
        pass


# TODO: Expose search provider as a configurable parameter.
class WebSearchAgentTool(Tools):
    description = "Search the web with DuckDuckGo HTML results."

    def __init__(self) -> None:
        # TODO: Allow users to specify query parameters, like safe search.
        super().__init__("web_search")

    def __call__(self) -> None:
        # TODO: Add caching for repeated queries.
        pass


# TODO: Add support for fetching multiple pages in batch.
class WebFetchAgentTool(Tools):
    description = "Fetch a web page and convert it into a readable excerpt."

    def __init__(self) -> None:
        # TODO: Allow selection of excerpt length or content focus (e.g., summary, main body).
        super().__init__("web_fetch")
        self._tool = WebFetchTool()

    def __call__(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult:
        # TODO: Catch and handle network or parsing errors.
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
