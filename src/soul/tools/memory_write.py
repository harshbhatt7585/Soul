from __future__ import annotations

from soul.tools.base import ToolContext, ToolResult


class MemoryWriteTool:
    name = "memory_write"
    description = "Write a note, preference, or outcome into local memory."

    def run(self, context: ToolContext, input_data: dict[str, object]) -> ToolResult:
        entry = context.memory.add(
            kind=str(input_data.get("kind", "note")),
            content=str(input_data.get("content", "")).strip(),
            tags=[str(tag) for tag in input_data.get("tags", [])] if isinstance(input_data.get("tags"), list) else [],
        )
        return ToolResult(
            summary=f"Saved memory entry {entry.id}.",
            output=entry.to_dict(),
        )
