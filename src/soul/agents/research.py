from __future__ import annotations

import re

from soul.config import Settings
from soul.llm import OllamaResearchSynthesizer
from soul.models import ResearchReport, SearchResult, SourceNote, utc_now_iso
from soul.tools import WebFetchTool, build_search_tool, extract_excerpt, extract_text_from_html
from soul.tools.base import FetchTool, SearchTool, Synthesizer


class ResearchAgent:
    def __init__(
        self,
        *,
        search_tool: SearchTool,
        fetch_tool: FetchTool,
        synthesizer: Synthesizer,
        settings: Settings,
    ) -> None:
        self._search_tool = search_tool
        self._fetch_tool = fetch_tool
        self._synthesizer = synthesizer
        self._settings = settings

    def plan_queries(self, prompt: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", prompt).strip()
        if not normalized:
            return []
        queries = [normalized]
        lowered = normalized.lower()
        if "compare" not in lowered and " vs " not in lowered:
            queries.append(f"{normalized} comparison")
        if not any(token in lowered for token in ("latest", "current", "2026", "today")):
            queries.append(f"latest {normalized}")
        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            key = query.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(query)
        return deduped[:3]

    def run(
        self,
        prompt: str,
        *,
        max_results: int = 5,
        max_pages: int = 3,
    ) -> ResearchReport:
        queries = self.plan_queries(prompt)
        warnings: list[str] = []
        if not queries:
            return ResearchReport(
                prompt=prompt,
                created_at=utc_now_iso(),
                queries=[],
                summary="Prompt was empty.",
                bullet_points=["Provide a non-empty research prompt."],
                sources=[],
                warnings=[],
                model="fallback",
            )

        search_hits = self._collect_hits(queries, max_results=max_results, warnings=warnings)
        sources = self._collect_sources(search_hits, max_pages=max_pages, warnings=warnings)
        synthesis = self._synthesizer.summarize(prompt, sources)
        warnings.extend(synthesis.warnings)

        return ResearchReport(
            prompt=prompt,
            created_at=utc_now_iso(),
            queries=queries,
            summary=synthesis.summary,
            bullet_points=synthesis.bullet_points,
            sources=sources,
            warnings=warnings,
            model=synthesis.model,
        )

    def _collect_hits(
        self,
        queries: list[str],
        *,
        max_results: int,
        warnings: list[str],
    ) -> list[tuple[str, SearchResult]]:
        collected: list[tuple[str, SearchResult]] = []
        seen_urls: set[str] = set()
        for query in queries:
            try:
                results = self._search_tool.search(query, limit=max_results)
            except Exception as exc:  # pylint: disable=broad-except
                warnings.append(f'Search failed for "{query}": {exc}')
                continue
            for result in results:
                if result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                collected.append((query, result))
        return collected

    def _collect_sources(
        self,
        search_hits: list[tuple[str, SearchResult]],
        *,
        max_pages: int,
        warnings: list[str],
    ) -> list[SourceNote]:
        sources: list[SourceNote] = []
        for query, hit in search_hits[:max_pages]:
            try:
                document = self._fetch_tool.fetch(hit.url)
                if "html" in document.content_type or document.content_type.startswith("text/"):
                    text = extract_text_from_html(
                        document.body,
                        limit_chars=self._settings.max_excerpt_chars * 2,
                    )
                    excerpt = extract_excerpt(
                        text,
                        max_chars=self._settings.max_excerpt_chars,
                    )
                else:
                    excerpt = document.body[: self._settings.max_excerpt_chars].strip()

                title = document.title or hit.title
                if document.truncated:
                    warnings.append(f"Truncated large document while reading {hit.url}")
                sources.append(
                    SourceNote(
                        query=query,
                        title=title,
                        url=hit.url,
                        snippet=hit.snippet,
                        excerpt=excerpt,
                        source=hit.source,
                        content_type=document.content_type,
                        fetched=True,
                    )
                )
            except Exception as exc:  # pylint: disable=broad-except
                warnings.append(f"Fetch failed for {hit.url}: {exc}")
                sources.append(
                    SourceNote(
                        query=query,
                        title=hit.title,
                        url=hit.url,
                        snippet=hit.snippet,
                        excerpt=hit.snippet,
                        source=hit.source,
                        fetched=False,
                    )
                )

        if sources:
            return sources

        return [
            SourceNote(
                query=query,
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                excerpt=hit.snippet,
                source=hit.source,
                fetched=False,
            )
            for query, hit in search_hits[:max_pages]
        ]


def build_research_agent(settings: Settings) -> ResearchAgent:
    return ResearchAgent(
        search_tool=build_search_tool(settings),
        fetch_tool=WebFetchTool(settings),
        synthesizer=OllamaResearchSynthesizer(settings),
        settings=settings,
    )
