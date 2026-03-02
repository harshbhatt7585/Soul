from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.config import Settings


class LLMHandler:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_models(self) -> list[str]:
        request = Request(
            f"{self._settings.ollama_base_url}/api/tags",
            headers={"User-Agent": self._settings.user_agent},
        )
        try:
            with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raise RuntimeError(f"Ollama tags request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to reach Ollama at {self._settings.ollama_base_url}") from exc

        models = payload.get("models", [])
        if not isinstance(models, list):
            return []
        return [str(item.get("name", "")).strip() for item in models if str(item.get("name", "")).strip()]

    def chat(self, *, model: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.2},
        }
        request = Request(
            f"{self._settings.ollama_base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self._settings.user_agent,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
                parsed = json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raise RuntimeError(f"Ollama chat request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to reach Ollama at {self._settings.ollama_base_url}") from exc

        message = parsed.get("message", {})
        if not isinstance(message, dict):
            raise RuntimeError("Ollama returned an invalid message payload")
        content = str(message.get("content", "")).strip()
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return str(parsed.get("model", model)).strip() or model, content


OllamaClient = LLMHandler
