from soul.tools.memory_read import MemoryReadTool
from soul.tools.memory_write import MemoryWriteTool
from soul.tools.registry import ToolRegistry
from soul.tools.web_fetch import WebFetchTool
from soul.tools.web_search import WebSearchTool


def create_default_registry() -> ToolRegistry:
    return (
        ToolRegistry()
        .register(MemoryReadTool())
        .register(MemoryWriteTool())
        .register(WebSearchTool())
        .register(WebFetchTool())
    )


__all__ = ["create_default_registry", "ToolRegistry"]
