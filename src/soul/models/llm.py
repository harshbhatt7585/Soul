from __future__ import annotations

from abc import ABC, abstractmethod
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.config import AgentConfig


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, *, model: str, system: str, prompt: str) -> str:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    def __init__(self, config: AgentConfig) -> None:
        self._config = config

    def generate(self, *, model: str, system: str, prompt: str) -> str:
        payload = {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        request = Request(
            f"{self._config.ollama_base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self._config.user_agent,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._config.request_timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama request failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to reach Ollama at {self._config.ollama_base_url}: {exc}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid response from Ollama: {body[:500]}") from exc

        response_text = parsed.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError(f"Ollama returned no text response: {body[:500]}")
        return response_text.strip()


class LLMHandler:
    def __init__(self, config: AgentConfig, provider: LLMProvider | None = None) -> None:
        self._config = config
        self._provider = provider or OllamaProvider(config)

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def generate(self, *, model: str, system: str, prompt: str) -> str:
        return self._provider.generate(model=model, system=system, prompt=prompt)


__all__ = ["LLMHandler", "LLMProvider", "OllamaProvider"]
