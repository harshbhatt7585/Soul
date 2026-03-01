from __future__ import annotations

from soul.agent.prompts import build_system_prompt, build_user_prompt, load_identity
from soul.agent.types import ToolTrace, ValidationResult
from soul.config import Settings, model_for_mode
from soul.model.llm import OllamaClient
from soul.storage.memory import MemoryEntry
from soul.utils.text import truncate


class Responder:
    def __init__(self, settings: Settings, llm_client: OllamaClient) -> None:
        self._settings = settings
        self._llm_client = llm_client

    def respond(
        self,
        *,
        prompt: str,
        mode: str,
        memories: list[MemoryEntry],
        traces: list[ToolTrace],
        validation: ValidationResult,
        model_override: str | None = None,
    ) -> tuple[str, str]:
        selected_model = model_for_mode(self._settings, mode, model_override)
        identity = load_identity(self._settings)
        agent_name = str(identity.get("name", "Soul")).strip() or "Soul"
        system_prompt = build_system_prompt(
            self._settings,
            mode=mode,
            name=agent_name,
            memories=memories,
            traces=traces,
            validation_reasons=validation.reasons,
        )
        user_prompt = build_user_prompt(prompt, traces)

        try:
            return self._llm_client.chat(
                model=selected_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as exc:  # pylint: disable=broad-except
            tool_lines = [f"- {trace.name}: {trace.summary}" for trace in traces] or ["- none"]
            fallback = [
                f"Soul could not reach the local model layer: {exc}",
                "",
                f"Mode: {mode}",
                f"Request: {prompt}",
                "",
                "Validation:",
                *[f"- {reason}" for reason in validation.reasons],
                "",
                "Tool context:",
                *tool_lines,
                "",
                "Next step: start Ollama, pull the configured models, and rerun the command.",
            ]
            return selected_model, truncate("\n".join(fallback), 4_000)
