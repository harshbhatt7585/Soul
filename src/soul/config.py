from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

DEFAULT_MANUAL_MODEL = "llama3.2:1b"
DEFAULT_AUTONOMOUS_MODEL = "qwen2.5:0.5b"
DEFAULT_RESEARCH_MODEL = "llama3.2:1b"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class AgentConfig:
    workspace_root: Path
    soul_home: Path
    scratchpad_path: Path
    identity_path: Path
    profile_path: Path
    ollama_base_url: str
    manual_model: str
    autonomous_model: str
    research_model: str
    request_timeout_seconds: float
    max_document_bytes: int
    max_excerpt_chars: int
    search_limit: int
    user_agent: str


def load_agent_config(workspace_root: Path | None = None) -> AgentConfig:
    root = Path(workspace_root or os.getcwd()).resolve()
    soul_home = root / ".soul"

    return AgentConfig(
        workspace_root=root,
        soul_home=soul_home,
        scratchpad_path=soul_home / "scratchpad.jsonl",
        identity_path=soul_home / "identity.json",
        profile_path=root / "SOUL.md",
        ollama_base_url=os.environ.get("SOUL_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        manual_model=os.environ.get("SOUL_MANUAL_MODEL", DEFAULT_MANUAL_MODEL),
        autonomous_model=os.environ.get("SOUL_AUTONOMOUS_MODEL", DEFAULT_AUTONOMOUS_MODEL),
        research_model=os.environ.get("SOUL_RESEARCH_MODEL", DEFAULT_RESEARCH_MODEL),
        request_timeout_seconds=_env_float("SOUL_REQUEST_TIMEOUT_SECONDS", 20.0),
        max_document_bytes=_env_int("SOUL_MAX_DOCUMENT_BYTES", 1_500_000),
        max_excerpt_chars=_env_int("SOUL_MAX_EXCERPT_CHARS", 4_000),
        search_limit=_env_int("SOUL_SEARCH_LIMIT", 5),
        user_agent=os.environ.get("SOUL_USER_AGENT", "soul/0.1 (+https://github.com/harshbhatt/soul)"),
    )


def model_for_mode(config: AgentConfig, mode: str, override: str | None = None) -> str:
    if override:
        return override
    if mode == "autonomous":
        return config.autonomous_model
    return config.manual_model


Settings = AgentConfig
load_settings = load_agent_config
