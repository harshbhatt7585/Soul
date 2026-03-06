from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from soul.config import AgentConfig


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


@dataclass(slots=True)
class MemoryEntry:
    id: str
    kind: str
    text: str
    tags: list[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "tags": self.tags,
            "created_at": self.created_at,
        }


class MemoryStore:
    def __init__(self, config: AgentConfig) -> None:
        self._path = config.memory_path

    def ensure_ready(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
        return self._path

    def append(self, *, text: str, kind: str, tags: list[str]) -> MemoryEntry:
        entry = MemoryEntry(
            id=str(uuid4()),
            kind=kind,
            text=text,
            tags=tags,
            created_at=datetime.now(UTC).isoformat(),
        )
        self.ensure_ready()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=True) + "\n")
        return entry

    def reset(self) -> None:
        self.ensure_ready()
        self._path.write_text("", encoding="utf-8")

    def all(self) -> list[MemoryEntry]:
        self.ensure_ready()
        entries: list[MemoryEntry] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            raw_tags = payload.get("tags", [])
            tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()] if isinstance(raw_tags, list) else []
            entries.append(
                MemoryEntry(
                    id=str(payload.get("id", "")),
                    kind=str(payload.get("kind", "note")).strip() or "note",
                    text=text,
                    tags=tags,
                    created_at=str(payload.get("created_at", "")),
                )
            )
        return entries

    def search(self, *, query: str, limit: int) -> list[MemoryEntry]:
        query_tokens = _tokenize(query)
        entries = self.all()
        scored: list[tuple[int, int, MemoryEntry]] = []
        for idx, entry in enumerate(entries):
            haystack = " ".join([entry.text, entry.kind, " ".join(entry.tags)])
            entry_tokens = _tokenize(haystack)
            overlap = len(query_tokens & entry_tokens)
            if query_tokens and overlap == 0:
                continue
            scored.append((overlap, idx, entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in scored[:limit]]


__all__ = ["MemoryEntry", "MemoryStore"]
