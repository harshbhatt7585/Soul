from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

AgentMode = Literal["manual", "autonomous"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LLMReply:
    model: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MemoryEntry:
    kind: str
    content: str
    created_at: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AssistantReply:
    prompt: str
    mode: AgentMode
    model: str
    reply: str
    created_at: str
    memories: list[MemoryEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "mode": self.mode,
            "model": self.model,
            "reply": self.reply,
            "created_at": self.created_at,
            "memories": [memory.to_dict() for memory in self.memories],
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FetchedDocument:
    url: str
    status_code: int
    content_type: str
    title: str
    body: str
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceNote:
    query: str
    title: str
    url: str
    snippet: str
    excerpt: str
    source: str = ""
    content_type: str = ""
    fetched: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SynthesisResult:
    summary: str
    bullet_points: list[str]
    model: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResearchReport:
    prompt: str
    created_at: str
    queries: list[str]
    summary: str
    bullet_points: list[str]
    sources: list[SourceNote]
    warnings: list[str] = field(default_factory=list)
    model: str = "fallback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "created_at": self.created_at,
            "queries": self.queries,
            "summary": self.summary,
            "bullet_points": self.bullet_points,
            "sources": [source.to_dict() for source in self.sources],
            "warnings": self.warnings,
            "model": self.model,
        }
