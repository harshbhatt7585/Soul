from __future__ import annotations

from html import unescape
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from soul.tools.base import ToolContext, ToolResult
from soul.utils.text import normalize_whitespace, truncate

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
    return normalize_whitespace(unescape(TAG_PATTERN.sub(" ", value)))


def _resolve_duckduckgo_url(raw_url: str) -> str:
    if raw_url.startswith("//"):
        raw_url = f"https:{raw_url}"
    parsed = urlparse(raw_url)
    query = parse_qs(parsed.query)
    if "uddg" in query:
        return unquote(query["uddg"][0])
    return raw_url


class WebSearchTool:
    name = "web_search"
    description = "Search the web with DuckDuckGo HTML results."

    def run(self, context: ToolContext, input_data: dict[str, object]) -> ToolResult:
        query = str(input_data.get("query", "")).strip()
        limit = int(input_data.get("limit", context.settings.search_limit))
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        request = Request(
            url,
            headers={
                "User-Agent": context.settings.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                "Accept-Encoding": "identity",
            },
        )
        with urlopen(request, timeout=context.settings.request_timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        results: list[dict[str, str]] = []
        for match in RESULT_ANCHOR_PATTERN.finditer(body):
            if len(results) >= limit:
                break
            href = _resolve_duckduckgo_url(match.group("href"))
            title = truncate(_strip_tags(match.group("title")), 140)
            tail = body[match.end() : match.end() + 1_500]
            snippet_match = SNIPPET_PATTERN.search(tail)
            snippet = truncate(_strip_tags(snippet_match.group("snippet")) if snippet_match else "", 280)
            if href and title:
                results.append({"title": title, "url": href, "snippet": snippet})

        return ToolResult(
            summary=f"Collected {len(results)} search hit(s) for '{query}'." if results else "No search hits returned.",
            output={"query": query, "hits": results},
        )
