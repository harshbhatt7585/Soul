from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from soul.config import Settings


def _tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", value.lower())}


def _make_id(prefix: str) -> str:
    from time import time_ns

    return f"{prefix}_{time_ns()}"


@dataclass(slots=True)
class MemoryEntry:
    id: str
    kind: str
    content: str
    tags: list[str]
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class MemoryStore:
    def __init__(self, settings: Settings) -> None:
        self._path = settings.memory_path

    def ensure_ready(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
        return self._path

    def read_all(self) -> list[MemoryEntry]:
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
            entries.append(
                MemoryEntry(
                    id=str(payload.get("id", _make_id("mem"))),
                    kind=str(payload.get("kind", "note")),
                    content=str(payload.get("content", "")),
                    tags=[str(tag) for tag in payload.get("tags", []) if str(tag).strip()],
                    created_at=str(payload.get("created_at", "")),
                )
            )
        return entries

    def add(self, *, kind: str, content: str, tags: list[str] | None = None) -> MemoryEntry:
        self.ensure_ready()
        entry = MemoryEntry(
            id=_make_id("mem"),
            kind=kind,
            content=content.strip(),
            tags=sorted({tag.strip().lower() for tag in (tags or []) if tag.strip()}),
            created_at=__import__("datetime").datetime.utcnow().isoformat() + "Z",
        )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=True) + "\n")
        return entry

    def recent(self, limit: int = 6) -> list[MemoryEntry]:
        return list(reversed(self.read_all()[-limit:]))

    def search(self, query: str, limit: int = 6) -> list[MemoryEntry]:
        entries = self.read_all()
        tokens = _tokenize(query)
        if not tokens:
            return self.recent(limit=limit)

        scored: list[tuple[int, MemoryEntry]] = []
        for entry in entries:
            haystack = " ".join([entry.kind, *entry.tags, entry.content]).lower()
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, entry))

        if not scored:
            return self.recent(limit=limit)

        scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return [entry for _, entry in scored[:limit]]
