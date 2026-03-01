from __future__ import annotations

from html import unescape
import json
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from soul.config import Settings
from soul.tools.base import SearchTool
from soul.models import SearchResult

RESULT_ANCHOR_PATTERN = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    flags=re.IGNORECASE | re.DOTALL,
)
SNIPPET_PATTERN = re.compile(
    r'<(?:a|div)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>.*?)</(?:a|div)>',
    flags=re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_PATTERN.sub(" ", value))).strip()


def _resolve_duckduckgo_url(raw_url: str) -> str:
    if raw_url.startswith("//"):
        raw_url = f"https:{raw_url}"
    parsed = urlparse(raw_url)
    query = parse_qs(parsed.query)
    if "uddg" in query:
        return unquote(query["uddg"][0])
    return raw_url


class DuckDuckGoSearchTool:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        request = Request(
            url,
            headers={
                "User-Agent": self._settings.request_user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                "Accept-Encoding": "identity",
            },
        )
        with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        matches = list(RESULT_ANCHOR_PATTERN.finditer(body))
        results: list[SearchResult] = []
        for match in matches:
            if len(results) >= limit:
                break
            href = _resolve_duckduckgo_url(match.group("href"))
            title = _strip_tags(match.group("title"))
            tail = body[match.end() : match.end() + 1_500]
            snippet_match = SNIPPET_PATTERN.search(tail)
            snippet = _strip_tags(snippet_match.group("snippet")) if snippet_match else ""
            if not href or not title:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=href,
                    snippet=snippet,
                    source="duckduckgo",
                )
            )
        return results


class SerperSearchTool:
    def __init__(self, settings: Settings) -> None:
        if not settings.serper_api_key:
            raise RuntimeError("SERPER_API_KEY is not set")
        self._settings = settings

    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        payload = json.dumps({"q": query, "num": limit}).encode("utf-8")
        request = Request(
            "https://google.serper.dev/search",
            data=payload,
            headers={
                "User-Agent": self._settings.request_user_agent,
                "Content-Type": "application/json",
                "X-API-KEY": self._settings.serper_api_key or "",
            },
            method="POST",
        )
        with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        results: list[SearchResult] = []
        for item in parsed.get("organic", [])[:limit]:
            link = str(item.get("link", "")).strip()
            title = str(item.get("title", "")).strip()
            if not link or not title:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=link,
                    snippet=str(item.get("snippet", "")).strip(),
                    source="serper",
                )
            )
        return results


def build_search_tool(settings: Settings) -> SearchTool:
    if settings.serper_api_key:
        return SerperSearchTool(settings)
    return DuckDuckGoSearchTool(settings)
