from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.config import Settings
from soul.models import FetchedDocument
from soul.tools.scrape import extract_title


class WebFetchTool:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch(self, url: str) -> FetchedDocument:
        request = Request(
            url,
            headers={
                "User-Agent": self._settings.request_user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
                status_code = getattr(response, "status", 200)
                payload = response.read(self._settings.max_document_bytes + 1)
                truncated = len(payload) > self._settings.max_document_bytes
                payload = payload[: self._settings.max_document_bytes]
                charset = response.headers.get_content_charset() or "utf-8"
                content_type = response.headers.get_content_type()
        except HTTPError as exc:
            raise RuntimeError(f"{url} returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to fetch {url}: {exc.reason}") from exc

        try:
            body = payload.decode(charset, errors="replace")
        except LookupError:
            body = payload.decode("utf-8", errors="replace")

        title = extract_title(body) if "html" in content_type else url
        return FetchedDocument(
            url=url,
            status_code=status_code,
            content_type=content_type,
            title=title,
            body=body,
            truncated=truncated,
        )
