from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re

SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas"}
BLOCK_TAGS = {
    "article",
    "aside",
    "blockquote",
    "br",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "header",
    "li",
    "main",
    "p",
    "section",
    "tr",
}


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data.strip():
            self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def normalize_whitespace(text: str) -> str:
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_html(html: str, *, limit_chars: int = 12_000) -> str:
    parser = _ReadableHTMLParser()
    parser.feed(html)
    text = normalize_whitespace(parser.get_text())
    return text[:limit_chars].strip()


def extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", match.group(1)))


def extract_excerpt(text: str, *, max_chars: int = 4_000) -> str:
    paragraphs = [part.strip() for part in text.split("\n\n")]
    filtered = [part for part in paragraphs if len(part) >= 60]
    if not filtered and text.strip():
        filtered = [text.strip()]
    excerpt = "\n\n".join(filtered[:4])
    return excerpt[:max_chars].strip()
