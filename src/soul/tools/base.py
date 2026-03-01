from __future__ import annotations

from typing import Protocol

from soul.models import FetchedDocument, SearchResult, SourceNote, SynthesisResult


class SearchTool(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]: ...


class FetchTool(Protocol):
    def fetch(self, url: str) -> FetchedDocument: ...


class Synthesizer(Protocol):
    def summarize(self, prompt: str, sources: list[SourceNote]) -> SynthesisResult: ...
