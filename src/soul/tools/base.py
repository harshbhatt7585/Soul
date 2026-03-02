from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from soul.agent.scratchpad import ScratchpadStore
from soul.config import Settings


@dataclass(slots=True)
class ToolContext:
    settings: Settings
    scratchpad: ScratchpadStore


@dataclass(slots=True)
class ToolResult:
    summary: str
    output: Any


class Tool(Protocol):
    name: str
    description: str

    def run(self, context: ToolContext, input_data: dict[str, Any]) -> ToolResult: ...
