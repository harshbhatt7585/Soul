from __future__ import annotations

from abc import ABC, abstractmethod
from html.parser import HTMLParser
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.config import AgentConfig


class Tools(ABC):
    description = ""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return " ".join(self._parts)


class MemoryRecallAgentTool(Tools):
    description = "Recall relevant memory entries for the current prompt."

    def __init__(self) -> None:
        super().__init__("memory_recall")

    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "tool": self.name, "error": "memory recall is not implemented yet"}


class MemoryWriteAgentTool(Tools):
    description = "Write a note, preference, or outcome into local memory."

    def __init__(self) -> None:
        super().__init__("memory_write")

    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "tool": self.name, "error": "memory write is not implemented yet"}


class WebSearchAgentTool(Tools):
    description = "Search the web with DuckDuckGo HTML results."

    def __init__(self) -> None:
        super().__init__("web_search")

    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "tool": self.name, "error": "missing query"}
        return {
            "ok": False,
            "tool": self.name,
            "error": "web search is not implemented yet",
            "query": query,
        }


class WebFetchAgentTool(Tools):
    description = "Fetch a web page and convert it into a readable excerpt."

    def __init__(self, config: AgentConfig) -> None:
        super().__init__("web_fetch")
        self._config = config

    def __call__(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url", "")).strip()
        if not url:
            return {"ok": False, "tool": self.name, "error": "missing url"}

        request = Request(url, headers={"User-Agent": self._config.user_agent}, method="GET")
        try:
            with urlopen(request, timeout=self._config.request_timeout_seconds) as response:
                raw = response.read(self._config.max_document_bytes)
                content_type = response.headers.get("Content-Type", "")
        except HTTPError as exc:
            return {"ok": False, "tool": self.name, "error": f"HTTP {exc.code} while fetching {url}"}
        except URLError as exc:
            return {"ok": False, "tool": self.name, "error": f"network error while fetching {url}: {exc}"}

        text = raw.decode("utf-8", errors="replace")
        if "html" in content_type.lower():
            parser = _HTMLTextExtractor()
            parser.feed(text)
            text = parser.text()

        excerpt = " ".join(text.split())[: self._config.max_excerpt_chars]
        return {
            "ok": True,
            "tool": self.name,
            "url": url,
            "content_type": content_type,
            "excerpt": excerpt,
        }


def build_default_tools(config: AgentConfig) -> list[Tools]:
    return [
        MemoryRecallAgentTool(),
        MemoryWriteAgentTool(),
        WebSearchAgentTool(),
        WebFetchAgentTool(config),
    ]


def get_tools() -> list[str]:
    return [
        f"{tool_cls.name}: {tool_cls.description}"  # type: ignore[attr-defined]
        for tool_cls in [
            MemoryRecallAgentTool(),
            MemoryWriteAgentTool(),
            WebSearchAgentTool(),
        ]
    ] + [f"web_fetch: {WebFetchAgentTool.description}"]


def format_tool_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=True)


__all__ = [
    "Tools",
    "MemoryRecallAgentTool",
    "MemoryWriteAgentTool",
    "WebSearchAgentTool",
    "WebFetchAgentTool",
    "build_default_tools",
    "format_tool_result",
    "get_tools",
]
