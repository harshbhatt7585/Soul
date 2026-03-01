from soul.agent.tools import build_default_tools
from soul.tools.registry import ToolRegistry


def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in build_default_tools():
        registry.register(tool)
    return registry


__all__ = ["create_default_registry", "ToolRegistry"]
