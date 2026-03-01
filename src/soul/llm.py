from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from soul.config import Settings
from soul.models import ChatMessage, LLMReply, SourceNote, SynthesisResult


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            f"{self._settings.ollama_base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self._settings.request_user_agent,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to reach Ollama at {self._settings.ollama_base_url}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Ollama returned an unexpected response payload")
        return parsed

    def _get_json(self, path: str) -> dict[str, object]:
        request = Request(
            f"{self._settings.ollama_base_url}{path}",
            headers={"User-Agent": self._settings.request_user_agent},
        )
        try:
            with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to reach Ollama at {self._settings.ollama_base_url}") from exc

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Ollama returned an unexpected response payload")
        return parsed

    def is_available(self) -> bool:
        try:
            self.list_models()
        except RuntimeError:
            return False
        return True

    def list_models(self) -> list[str]:
        parsed = self._get_json("/api/tags")
        models = parsed.get("models", [])
        if not isinstance(models, list):
            return []
        discovered: list[str] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if name:
                discovered.append(name)
        return discovered

    def chat(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> LLMReply:
        payload: dict[str, object] = {
            "model": model,
            "stream": False,
            "messages": [message.to_dict() for message in messages],
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        parsed = self._post_json("/api/chat", payload)
        message = parsed.get("message", {})
        if not isinstance(message, dict):
            raise RuntimeError("Ollama response did not include a message")
        content = str(message.get("content", "")).strip()
        if not content:
            raise RuntimeError("Ollama returned an empty message")
        model_name = str(parsed.get("model", model)).strip() or model
        return LLMReply(model=model_name, content=content)


class FallbackSynthesizer:
    def summarize(self, prompt: str, sources: list[SourceNote]) -> SynthesisResult:
        if not sources:
            return SynthesisResult(
                summary=f"No usable sources were collected for: {prompt}",
                bullet_points=[
                    "The search layer did not return fetchable pages.",
                    "Try a narrower prompt or provide a source domain.",
                ],
                model="fallback",
            )

        bullet_points = []
        for source in sources[:3]:
            detail = source.snippet or source.excerpt or "No preview text available."
            bullet_points.append(f"{source.title}: {detail[:220].strip()}")

        domains = sorted({source.source for source in sources if source.source})
        summary = (
            f"Collected {len(sources)} source(s) across {len(domains) or 1} search provider(s) "
            f"for: {prompt}"
        )
        return SynthesisResult(summary=summary, bullet_points=bullet_points, model="fallback")


class OllamaResearchSynthesizer:
    def __init__(self, settings: Settings, client: OllamaClient | None = None) -> None:
        self._settings = settings
        self._client = client or OllamaClient(settings)
        self._fallback = FallbackSynthesizer()

    def summarize(self, prompt: str, sources: list[SourceNote]) -> SynthesisResult:
        if not sources:
            return self._fallback.summarize(prompt, sources)

        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are a research synthesis engine. Return strict JSON with keys "
                    "summary and bullet_points. summary should be 2-4 sentences. "
                    "bullet_points should contain 3-5 concise findings grounded in the sources."
                ),
            ),
            ChatMessage(
                role="user",
                content=json.dumps(
                    {
                        "prompt": prompt,
                        "sources": [source.to_dict() for source in sources],
                    }
                ),
            ),
        ]

        try:
            reply = self._client.chat(
                model=self._settings.research_model,
                messages=messages,
                temperature=0.1,
                json_mode=True,
            )
            rendered = json.loads(reply.content)
            summary = str(rendered.get("summary", "")).strip()
            bullet_points = [
                str(item).strip()
                for item in rendered.get("bullet_points", [])
                if str(item).strip()
            ]
            if summary and bullet_points:
                return SynthesisResult(
                    summary=summary,
                    bullet_points=bullet_points,
                    model=reply.model,
                )
        except Exception as exc:  # pylint: disable=broad-except
            fallback = self._fallback.summarize(prompt, sources)
            fallback.warnings.append(f"Ollama synthesis failed: {exc}")
            return fallback

        fallback = self._fallback.summarize(prompt, sources)
        fallback.warnings.append("Ollama synthesis returned an empty payload.")
        return fallback
