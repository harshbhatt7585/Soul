from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AgentMode = Literal["manual", "autonomous"]


def now_iso() -> str:
    return __import__("datetime").datetime.utcnow().isoformat() + "Z"


@dataclass(slots=True)
class ToolCall:
    name: str
    input: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Plan:
    objective: str
    steps: list[str]
    tool_calls: list[ToolCall]

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "steps": self.steps,
            "tool_calls": [tool_call.to_dict() for tool_call in self.tool_calls],
        }


@dataclass(slots=True)
class ToolTrace:
    name: str
    summary: str
    output: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentEvent:
    kind: Literal["planning", "tool", "result"]
    title: str
    detail: str
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RunResult:
    prompt: str
    mode: AgentMode
    model: str
    reply: str
    plan: Plan
    tools: list[ToolTrace]
    events: list[AgentEvent]
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "mode": self.mode,
            "model": self.model,
            "reply": self.reply,
            "plan": self.plan.to_dict(),
            "tools": [tool.to_dict() for tool in self.tools],
            "events": [event.to_dict() for event in self.events],
            "created_at": self.created_at,
        }
