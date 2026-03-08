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


@dataclass(slots=True)
class FileMemoryMatch:
    path: str
    excerpt: str
    score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "excerpt": self.excerpt,
            "score": self.score,
        }


class MemoryStore:
    def __init__(self, config: AgentConfig) -> None:
        self._path = config.memory_path
        self._legacy_path = self._path.with_name("memory.jsonl")
        self._workspace_root = config.workspace_root
        self._max_excerpt_chars = config.max_excerpt_chars
        self._search_limit = config.search_limit

    def ensure_ready(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("", encoding="utf-8")
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
            handle.write(self._format_entry(entry))
        return entry

    def reset(self) -> None:
        self.ensure_ready()
        self._path.write_text("", encoding="utf-8")

    def all(self) -> list[MemoryEntry]:
        self.ensure_ready()
        entries = self._load_markdown_entries()
        entries.extend(self._load_legacy_jsonl_entries())
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

    def search_workspace(self, *, query: str, limit: int) -> list[FileMemoryMatch]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        matches: list[FileMemoryMatch] = []
        for path in self._iter_workspace_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            normalized = " ".join(text.split())
            if not normalized:
                continue

            score = len(query_tokens & _tokenize(normalized))
            if score == 0:
                continue

            excerpt = self._build_excerpt(normalized, query_tokens)
            matches.append(
                FileMemoryMatch(
                    path=str(path.relative_to(self._workspace_root)),
                    excerpt=excerpt,
                    score=score,
                )
            )

        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[:limit]

    def _iter_workspace_files(self) -> list[Path]:
        ignored_dirs = {
            ".git",
            ".venv",
            "__pycache__",
            "node_modules",
            ".mypy_cache",
            ".pytest_cache",
            ".soul",
        }
        ignored_suffixes = {
            ".pyc",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
            ".db",
        }

        files: list[Path] = []
        for path in self._workspace_root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in ignored_dirs for part in path.parts):
                continue
            if path.suffix.lower() in ignored_suffixes:
                continue
            files.append(path)
        return files

    def _build_excerpt(self, text: str, query_tokens: set[str]) -> str:
        words = text.split()
        for idx, word in enumerate(words):
            token = re.sub(r"[^a-z0-9]", "", word.lower())
            if token in query_tokens:
                start = max(0, idx - 20)
                end = min(len(words), idx + 20)
                excerpt = " ".join(words[start:end])
                return excerpt[: self._max_excerpt_chars]
        return text[: self._max_excerpt_chars]

    def _format_entry(self, entry: MemoryEntry) -> str:
        return entry.text.strip() + "\n\n"

    def _load_markdown_entries(self) -> list[MemoryEntry]:
        raw = self._path.read_text(encoding="utf-8")
        entries: list[MemoryEntry] = []
        for block in re.split(r"\n\s*\n+", raw):
            entry = self._parse_markdown_block(block)
            if entry is not None:
                entries.append(entry)
        return entries

    def _parse_markdown_block(self, block: str) -> MemoryEntry | None:
        content = block.strip()
        if not content:
            return None

        if not content.startswith("## Memory"):
            return MemoryEntry(
                id=str(uuid4()),
                kind="note",
                text=content,
                tags=[],
                created_at="",
            )

        lines = [line.rstrip() for line in content.splitlines()]
        meta: dict[str, str] = {}
        text_lines: list[str] = []
        in_text = False
        for line in lines:
            if in_text:
                text_lines.append(line)
                continue
            if line == "text:":
                in_text = True
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()

        text = "\n".join(text_lines).strip()
        if not text:
            return None

        raw_tags = meta.get("tags", "")
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        return MemoryEntry(
            id=meta.get("id", str(uuid4())),
            kind=meta.get("kind", "note") or "note",
            text=text,
            tags=tags,
            created_at=meta.get("created_at", ""),
        )

    def _load_legacy_jsonl_entries(self) -> list[MemoryEntry]:
        if not self._legacy_path.exists():
            return []

        entries: list[MemoryEntry] = []
        for line in self._legacy_path.read_text(encoding="utf-8").splitlines():
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


__all__ = ["FileMemoryMatch", "MemoryEntry", "MemoryStore"]
