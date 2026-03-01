from __future__ import annotations

from soul.agent.types import AgentEvent, Plan, ToolTrace
from soul.agent.scratchpad import ScratchpadStore
from soul.storage.memory import MemoryEntry, MemoryStore
from soul.tools import ToolRegistry
from soul.tools.base import ToolContext


class Executor:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        context: ToolContext,
        memory_store: MemoryStore,
        scratchpad: ScratchpadStore,
    ) -> None:
        self._registry = registry
        self._context = context
        self._memory_store = memory_store
        self._scratchpad = scratchpad

    def execute(self, plan: Plan) -> tuple[list[ToolTrace], list[AgentEvent], list[MemoryEntry]]:
        traces: list[ToolTrace] = []
        events: list[AgentEvent] = []
        memories: list[MemoryEntry] = []

        for tool_call in plan.tool_calls:
            try:
                result = self._registry.run(tool_call.name, self._context, tool_call.input)
            except Exception as exc:  # pylint: disable=broad-except
                event = AgentEvent(kind="tool", title=f"{tool_call.name} failed", detail=str(exc))
                events.append(event)
                self._scratchpad.append(event)
                continue

            trace = ToolTrace(name=tool_call.name, summary=result.summary, output=result.output)
            traces.append(trace)
            event = AgentEvent(kind="tool", title=tool_call.name, detail=result.summary)
            events.append(event)
            self._scratchpad.append(event)

            if tool_call.name == "memory_recall" and isinstance(result.output, list):
                memories = [
                    MemoryEntry(
                        id=str(item.get("id", "")),
                        kind=str(item.get("kind", "note")),
                        content=str(item.get("content", "")),
                        tags=[str(tag) for tag in item.get("tags", [])],
                        created_at=str(item.get("created_at", "")),
                    )
                    for item in result.output
                    if isinstance(item, dict)
                ]
                memory_event = AgentEvent(
                    kind="memory",
                    title="Memory recall",
                    detail=f"Loaded {len(memories)} memory item(s).",
                )
                events.append(memory_event)
                self._scratchpad.append(memory_event)

            if tool_call.name == "web_search" and isinstance(result.output, dict):
                hits = result.output.get("hits", [])
                if isinstance(hits, list):
                    for hit in hits[:2]:
                        if not isinstance(hit, dict) or not str(hit.get("url", "")).strip():
                            continue
                        try:
                            fetched = self._registry.run("web_fetch", self._context, {"url": str(hit["url"])})
                        except Exception as exc:  # pylint: disable=broad-except
                            fetch_event = AgentEvent(kind="tool", title="web_fetch failed", detail=str(exc))
                            events.append(fetch_event)
                            self._scratchpad.append(fetch_event)
                            continue
                        fetch_trace = ToolTrace(name="web_fetch", summary=fetched.summary, output=fetched.output)
                        traces.append(fetch_trace)
                        fetch_event = AgentEvent(kind="tool", title="web_fetch", detail=fetched.summary)
                        events.append(fetch_event)
                        self._scratchpad.append(fetch_event)

        return traces, events, memories
