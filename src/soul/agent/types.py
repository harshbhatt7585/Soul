from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


def now_iso() -> str:
    return __import__("datetime").datetime.utcnow().isoformat() + "Z"


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
    reply: str
    mode: str | None = None
    model: str | None = None
    events: list[AgentEvent] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
