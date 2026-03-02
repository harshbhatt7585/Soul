from __future__ import annotations

import json
from pathlib import Path

from soul.agent.types import AgentEvent
from soul.config import AgentConfig


class ScratchpadStore:
    def __init__(self, config: AgentConfig) -> None:
        self._path = config.scratchpad_path

    def ensure_ready(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
        return self._path

    def append(self, event: AgentEvent) -> None:
        self.ensure_ready()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=True) + "\n")

    def recent(self, limit: int = 12) -> list[AgentEvent]:
        self.ensure_ready()
        events: list[AgentEvent] = []
        for line in self._path.read_text(encoding="utf-8").splitlines()[-limit:]:
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            events.append(
                AgentEvent(
                    kind=str(payload.get("kind", "planning")),  # type: ignore[arg-type]
                    title=str(payload.get("title", "")),
                    detail=str(payload.get("detail", "")),
                    created_at=str(payload.get("created_at", "")),
                )
            )
        return events
