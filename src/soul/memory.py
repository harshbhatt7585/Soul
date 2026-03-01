from __future__ import annotations

import json
from pathlib import Path
import re

from soul.config import Settings
from soul.models import MemoryEntry, utc_now_iso


def _tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 3}


class MemoryStore:
    def __init__(self, settings: Settings) -> None:
        self._path = settings.memory_file

    def ensure_ready(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
        return self._path

    def add(self, content: str, *, kind: str = "note", tags: list[str] | None = None) -> MemoryEntry:
        entry = MemoryEntry(
            kind=kind,
            content=content.strip(),
            created_at=utc_now_iso(),
            tags=sorted({tag.strip().lower() for tag in (tags or []) if tag.strip()}),
        )
        self.ensure_ready()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=True) + "\n")
        return entry

    def load_all(self) -> list[MemoryEntry]:
        if not self._path.exists():
            return []
        entries: list[MemoryEntry] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                entries.append(
                    MemoryEntry(
                        kind=str(payload.get("kind", "note")).strip() or "note",
                        content=str(payload.get("content", "")).strip(),
                        created_at=str(payload.get("created_at", "")),
                        tags=[
                            str(tag).strip()
                            for tag in payload.get("tags", [])
                            if str(tag).strip()
                        ],
                    )
                )
        return entries

    def recent(self, *, limit: int = 5) -> list[MemoryEntry]:
        entries = self.load_all()
        return list(reversed(entries[-limit:]))

    def search(self, query: str, *, limit: int = 5) -> list[MemoryEntry]:
        tokens = _tokenize(query)
        entries = self.load_all()
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
