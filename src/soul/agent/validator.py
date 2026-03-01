from __future__ import annotations

from soul.agent.types import Plan, ToolTrace, ValidationResult


class Validator:
    def validate(self, *, plan: Plan, traces: list[ToolTrace]) -> ValidationResult:
        reasons: list[str] = []
        memory_trace = next((trace for trace in traces if trace.name == "memory_recall"), None)
        has_memory = bool(memory_trace and isinstance(memory_trace.output, list) and memory_trace.output)
        has_research = any(trace.name in {"web_search", "web_fetch"} for trace in traces)

        if has_memory:
            reasons.append("Relevant memory was loaded.")
        else:
            reasons.append("No memory context was available.")

        if any(tool_call.name == "web_search" for tool_call in plan.tool_calls):
            if has_research:
                reasons.append("External context was gathered from the web.")
            else:
                reasons.append("Research was planned but external context was not gathered.")

        ready = has_memory or has_research or not plan.tool_calls
        return ValidationResult(ready=ready, reasons=reasons)
