from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.agent.scratchpad import ScratchpadStore
from soul.agent.tools import build_default_tools
from soul.agent.types import AgentEvent, RunResult
from soul.config import AgentConfig, model_for_mode
from soul.models.llm import LLMHandler

DEFAULT_SOUL_MD = """# Soul

Soul is a personal open-source CLI assistant that runs locally first.

## Identity

- Be pragmatic, concise, and explicit.
- Work with the user's current goal and available tools.
- Do not pretend work happened if no tool or model output supports it.
"""


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."


class SoulAgent:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._scratchpad = ScratchpadStore(config)
        self._llm_handler = LLMHandler(config)
        self._tools = build_default_tools()

    def _available_tools(self) -> list[str]:
        return [f"{tool.name}: {tool.description}" for tool in self._tools]

    def initialize_state(self, *, force_identity: bool = False) -> dict[str, object]:
        self._scratchpad.ensure_ready()
        self._config.soul_path.parent.mkdir(parents=True, exist_ok=True)
        if force_identity or not self._config.soul_path.exists():
            self._config.soul_path.write_text(DEFAULT_SOUL_MD + "\n", encoding="utf-8")
            soul_created = True
        else:
            soul_created = False
        return {
            "workspace_root": str(self._config.workspace_root),
            "soul_home": str(self._config.soul_home),
            "scratchpad_path": str(self._config.scratchpad_path),
            "soul_path": str(self._config.soul_path),
            "soul_created": soul_created,
        }

    def doctor(self) -> dict[str, object]:
        payload = self.initialize_state()
        available_models, error = self._list_ollama_models()
        required_models = sorted(
            {
                self._config.manual_model,
                self._config.autonomous_model,
                self._config.research_model,
            }
        )
        payload.update(
            {
                "ollama_base_url": self._config.ollama_base_url,
                "required_models": required_models,
                "available_models": available_models,
                "missing_models": [model for model in required_models if model not in available_models],
                "ollama_ok": error is None,
                "ollama_error": error,
            }
        )
        return payload

    def _append_event(self, event: AgentEvent, events: list[AgentEvent]) -> None:
        events.append(event)
        self._scratchpad.append(event)

    def _identity_text(self) -> str:
        if not self._config.soul_path.exists():
            return DEFAULT_SOUL_MD
        return self._config.soul_path.read_text(encoding="utf-8").strip() or DEFAULT_SOUL_MD

    def _recent_events_text(self, limit: int = 6) -> str:
        recent = self._scratchpad.recent(limit=limit)
        if not recent:
            return "- No prior scratchpad events."
        return "\n".join(
            f"- [{event.kind}] {event.title}: {_truncate(event.detail, 160)}"
            for event in recent
        )

    def _system_prompt(self, mode: str) -> str:
        tool_lines = "\n".join(f"- {tool}" for tool in self._available_tools())
        return (
            f"{self._identity_text()}\n\n"
            f"## Current Mode\n"
            f"- {mode}\n\n"
            f"## Available Tools\n"
            f"{tool_lines}\n\n"
            f"## Recent Scratchpad\n"
            f"{self._recent_events_text()}\n"
        )

    def _ollama_request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        method: str = "POST",
    ) -> dict[str, Any]:
        request = Request(
            f"{self._config.ollama_base_url}{path}",
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self._config.user_agent,
            },
            method=method,
        )
        with urlopen(request, timeout=self._config.request_timeout_seconds) as response:
            body = response.read().decode("utf-8")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Ollama returned a non-object response.")
        return data

    def _list_ollama_models(self) -> tuple[list[str], str | None]:
        try:
            payload = self._ollama_request("/api/tags", method="GET")
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return [], str(exc)

        raw_models = payload.get("models", [])
        if not isinstance(raw_models, list):
            return [], "Unexpected Ollama models payload."

        models: list[str] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name:
                models.append(name)
        return sorted(set(models)), None

    def _try_llm_handler(
        self,
        prompt: str,
        *,
        model: str,
        system_prompt: str,
    ) -> tuple[str | None, str | None]:
        for method_name in ("generate", "complete", "chat", "run"):
            method = getattr(self._llm_handler, method_name, None)
            if not callable(method):
                continue
            attempts = (
                lambda: method(prompt, model=model, system_prompt=system_prompt),
                lambda: method(prompt, model=model),
                lambda: method(system_prompt=system_prompt, prompt=prompt, model=model),
                lambda: method(prompt),
            )
            for attempt in attempts:
                try:
                    raw_reply = attempt()
                except TypeError:
                    continue
                except Exception as exc:  # pylint: disable=broad-except
                    return None, str(exc)
                if isinstance(raw_reply, str) and raw_reply.strip():
                    return raw_reply.strip(), None
                if isinstance(raw_reply, dict):
                    reply = raw_reply.get("reply") or raw_reply.get("response")
                    if isinstance(reply, str) and reply.strip():
                        return reply.strip(), None
                return None, "LLM handler returned an empty response."
        return None, None

    def _generate_reply(self, prompt: str, *, mode: str, model: str) -> tuple[str, str]:
        system_prompt = self._system_prompt(mode)

        handler_reply, handler_error = self._try_llm_handler(
            prompt,
            model=model,
            system_prompt=system_prompt,
        )
        if handler_reply:
            return handler_reply, f"provider=llm_handler model={model} status=ok"

        try:
            payload = self._ollama_request(
                "/api/generate",
                {
                    "model": model,
                    "system": system_prompt,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            reply = payload.get("response")
            if isinstance(reply, str) and reply.strip():
                return reply.strip(), f"provider=ollama model={model} status=ok"
            error = "Ollama returned an empty response."
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            error = str(exc)

        if handler_error:
            error = f"{handler_error}; {error}"

        return (
            (
                "I could not reach a local model, so I can only record the request right now.\n\n"
                f"Mode: {mode}\n"
                f"Model: {model}\n"
                f"Prompt: {prompt}"
            ),
            f"provider=fallback model={model} status=degraded error={_truncate(error, 180)}",
        )

    def run(self, prompt: str, *, mode: str = "manual", model: str | None = None) -> RunResult:
        normalized = prompt.strip()
        if not normalized:
            raise ValueError("Prompt must not be empty.")

        self.initialize_state()
        selected_model = model_for_mode(self._config, mode, model)
        events: list[AgentEvent] = []

        planning_event = AgentEvent(
            kind="planning",
            title="Run plan",
            detail=(
                f"mode={mode} | model={selected_model} | "
                "initialize_state | build_context | generate_reply"
            ),
        )
        self._append_event(planning_event, events)

        reply, tool_detail = self._generate_reply(normalized, mode=mode, model=selected_model)
        tool_event = AgentEvent(
            kind="tool",
            title="Model invocation",
            detail=tool_detail,
        )
        self._append_event(tool_event, events)

        result_event = AgentEvent(kind="result", title="Reply", detail=_truncate(reply, 200))
        self._append_event(result_event, events)

        return RunResult(
            prompt=normalized,
            reply=reply,
            mode=mode,
            model=selected_model,
            events=events,
        )
