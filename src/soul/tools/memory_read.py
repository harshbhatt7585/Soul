from __future__ import annotations

from soul.tools.base import ToolContext, ToolResult


class MemoryReadTool:
    name = "memory_recall"
    description = "Recall relevant memory entries for the current prompt."

    def run(self, context: ToolContext, input_data: dict[str, object]) -> ToolResult:
        query = str(input_data.get("query", "")).strip()
        limit = int(input_data.get("limit", 6))
        entries = context.memory.search(query, limit=limit)
        return ToolResult(
            summary=f"Loaded {len(entries)} memory item(s)." if entries else "No relevant memories found.",
            output=[entry.to_dict() for entry in entries],
        )
