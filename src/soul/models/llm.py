from __future__ import annotations

from abc import ABC, abstractmethod
import json
import re
import socket
from dataclasses import dataclass, field
from typing import Any, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.config import AgentConfig


class ChatMessage(TypedDict, total=False):
    role: str
    content: str
    name: str
    tool_calls: list[dict[str, Any]]


@dataclass(slots=True)
class ChatResponse:
    content: str
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _extract_reasoning(response_text: str, message: dict[str, Any]) -> tuple[str, str]:
    reasoning = message.get("thinking", message.get("reasoning_content", ""))
    if not isinstance(reasoning, str):
        reasoning = ""

    match = re.search(r"<think>\s*(.*?)\s*</think>", response_text, flags=re.DOTALL)
    if match:
        if not reasoning.strip():
            reasoning = match.group(1).strip()
        response_text = re.sub(r"<think>\s*.*?\s*</think>\s*", "", response_text, count=1, flags=re.DOTALL)

    return response_text.strip(), reasoning.strip()


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        format: str | None = None,
    ) -> ChatResponse:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    def __init__(self, config: AgentConfig) -> None:
        self._config = config

    def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        format: str | None = None,
    ) -> ChatResponse:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if format:
            payload["format"] = format
        request = Request(
            f"{self._config.ollama_base_url}/api/chat",
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
        except TimeoutError as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self._config.request_timeout_seconds:.0f}s for model {model}"
            ) from exc
        except socket.timeout as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self._config.request_timeout_seconds:.0f}s for model {model}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to reach Ollama at {self._config.ollama_base_url}: {exc}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid response from Ollama: {body[:500]}") from exc

        message = parsed.get("message", {})
        if not isinstance(message, dict):
            raise RuntimeError(f"Ollama returned no message payload: {body[:500]}")

        response_text = message.get("content", "")
        if not isinstance(response_text, str):
            response_text = ""
        response_text, reasoning = _extract_reasoning(response_text, message)

        tool_calls = message.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            tool_calls = []

        if not response_text.strip() and not tool_calls:
            raise RuntimeError(f"Ollama returned neither text nor tool calls: {body[:500]}")
        return ChatResponse(content=response_text, reasoning=reasoning, tool_calls=tool_calls)


class LLMHandler:
    def __init__(self, config: AgentConfig, provider: LLMProvider | None = None) -> None:
        self._config = config
        self._provider = provider or OllamaProvider(config)

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        format: str | None = None,
    ) -> ChatResponse:
        return self._provider.chat(model=model, messages=messages, tools=tools, format=format)


__all__ = ["ChatMessage", "ChatResponse", "LLMHandler", "LLMProvider", "OllamaProvider"]
