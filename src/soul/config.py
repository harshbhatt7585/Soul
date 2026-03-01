from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

DEFAULT_MANUAL_MODEL = "llama3.2:1b"
DEFAULT_AUTONOMOUS_MODEL = "qwen2.5:0.5b"
DEFAULT_RESEARCH_MODEL = "llama3.2:1b"


@dataclass(slots=True)
class Settings:
    workspace_root: Path
    soul_home: Path
    memory_file: Path
    identity_file: Path
    ollama_base_url: str
    manual_model: str
    autonomous_model: str
    research_model: str
    serper_api_key: str | None
    request_timeout_seconds: float
    request_user_agent: str
    max_document_bytes: int
    max_excerpt_chars: int


def _read_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _read_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def load_settings(workspace_root: Path | None = None) -> Settings:
    root = Path(workspace_root or os.getcwd()).resolve()
    soul_home = root / ".soul"
    return Settings(
        workspace_root=root,
        soul_home=soul_home,
        memory_file=soul_home / "memory.jsonl",
        identity_file=soul_home / "identity.json",
        ollama_base_url=_normalize_base_url(
            os.environ.get("SOUL_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ),
        manual_model=os.environ.get("SOUL_MANUAL_MODEL", DEFAULT_MANUAL_MODEL),
        autonomous_model=os.environ.get("SOUL_AUTONOMOUS_MODEL", DEFAULT_AUTONOMOUS_MODEL),
        research_model=os.environ.get("SOUL_RESEARCH_MODEL", DEFAULT_RESEARCH_MODEL),
        serper_api_key=os.environ.get("SERPER_API_KEY"),
        request_timeout_seconds=_read_float("SOUL_REQUEST_TIMEOUT_SECONDS", 20.0),
        request_user_agent=os.environ.get(
            "SOUL_USER_AGENT",
            "soul/0.1 (+https://github.com/harshbhatt/soul)",
        ),
        max_document_bytes=_read_int("SOUL_MAX_DOCUMENT_BYTES", 1_500_000),
        max_excerpt_chars=_read_int("SOUL_MAX_EXCERPT_CHARS", 4_000),
    )
