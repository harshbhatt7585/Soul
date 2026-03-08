from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:
    _load_dotenv = None

DEFAULT_MODEL = "qwen3.5:2b"


def _load_env_file(path: Path) -> None:
    if _load_dotenv is not None:
        _load_dotenv(path)
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _env_float(name: str, default: float) -> float:
    # TODO: Warn when invalid float env vars are ignored so configuration mistakes are visible.
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    # TODO: Warn when invalid integer env vars are ignored so configuration mistakes are visible.
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
    memory_path: Path
    soul_path: Path
    ollama_base_url: str
    ollama_keep_alive: str
    ollama_think: bool
    ollama_num_ctx: int
    ollama_temperature: float
    model: str
    request_timeout_seconds: float
    max_document_bytes: int
    max_excerpt_chars: int
    search_limit: int
    user_agent: str
    tavily_api_key: str


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def load_agent_config(workspace_root: Path | None = None) -> AgentConfig:
    # TODO: Support reading per-workspace config files in addition to environment variables.
    root = Path(workspace_root or os.getcwd()).resolve()
    _load_env_file(root / ".env")
    soul_home = root / ".soul"

    return AgentConfig(
        workspace_root=root,
        soul_home=soul_home,
        scratchpad_path=soul_home / "scratchpad.jsonl",
        memory_path=soul_home / "memory.jsonl",
        soul_path=root / "SOUL.md",
        ollama_base_url=os.environ.get("SOUL_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_keep_alive=os.environ.get("SOUL_OLLAMA_KEEP_ALIVE", "15m").strip() or "15m",
        ollama_think=_env_bool("SOUL_OLLAMA_THINK", False),
        ollama_num_ctx=_env_int("SOUL_OLLAMA_NUM_CTX", 2048),
        ollama_temperature=_env_float("SOUL_OLLAMA_TEMPERATURE", 0.7),
        model=os.environ.get("SOUL_MODEL", os.environ.get("SOUL_MANUAL_MODEL", DEFAULT_MODEL)),
        request_timeout_seconds=_env_float("SOUL_REQUEST_TIMEOUT_SECONDS", 120.0),
        max_document_bytes=_env_int("SOUL_MAX_DOCUMENT_BYTES", 1_500_000),
        max_excerpt_chars=_env_int("SOUL_MAX_EXCERPT_CHARS", 4_000),
        search_limit=_env_int("SOUL_SEARCH_LIMIT", 5),
        user_agent=os.environ.get("SOUL_USER_AGENT", "soul/0.1 (+https://github.com/harshbhatt/soul)"),
        tavily_api_key=os.environ.get("TAVILY_API_KEY", "").strip(),
    )


def model_for_mode(config: AgentConfig, mode: str, override: str | None = None) -> str:
    del mode
    if override:
        return override
    return config.model


Settings = AgentConfig
load_settings = load_agent_config
