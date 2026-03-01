from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.tools.base import ToolContext, ToolResult
from soul.utils.text import extract_title, strip_html, truncate


class WebFetchTool:
    name = "web_fetch"
    description = "Fetch a web page and convert it into a readable excerpt."

    def run(self, context: ToolContext, input_data: dict[str, object]) -> ToolResult:
        url = str(input_data.get("url", "")).strip()
        request = Request(
            url,
            headers={
                "User-Agent": context.settings.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urlopen(request, timeout=context.settings.request_timeout_seconds) as response:
                payload = response.read(context.settings.max_document_bytes + 1)
                content_type = response.headers.get_content_type()
                charset = response.headers.get_content_charset() or "utf-8"
        except HTTPError as exc:
            raise RuntimeError(f"{url} returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to fetch {url}: {exc.reason}") from exc

        truncated = len(payload) > context.settings.max_document_bytes
        payload = payload[: context.settings.max_document_bytes]
        try:
            body = payload.decode(charset, errors="replace")
        except LookupError:
            body = payload.decode("utf-8", errors="replace")

        title = extract_title(body) if "html" in content_type else url
        excerpt = truncate(strip_html(body), context.settings.max_excerpt_chars)
        output = {
            "url": url,
            "title": title or url,
            "content_type": content_type,
            "excerpt": excerpt,
            "truncated": truncated,
        }
        return ToolResult(summary=f"Fetched {output['title']}.", output=output)
