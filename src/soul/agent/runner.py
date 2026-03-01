from __future__ import annotations

import json

from soul.agent.prompts import load_identity
from soul.agent.responder import Responder
from soul.agent.scratchpad import ScratchpadStore
from soul.agent.planner import Planner
from soul.agent.types import AgentEvent, RunResult, ToolTrace
from soul.agent.validator import Validator
from soul.config import Settings
from soul.model.llm import OllamaClient
from soul.storage.memory import MemoryEntry, MemoryStore
from soul.tools import create_default_registry
from soul.tools.base import ToolContext
from soul.utils.text import truncate

DEFAULT_IDENTITY = {
    "name": "Soul",
    "role": "A personal open-source CLI assistant that runs locally first.",
    "principles": [
        "Prefer concrete next actions over abstract advice.",
        "Do not claim actions happened unless a tool or model output supports it.",
        "Use memory when it helps, but do not overfit to stale context.",
    ],
}


class SoulRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._memory = MemoryStore(settings)
        self._scratchpad = ScratchpadStore(settings)
        self._registry = create_default_registry()
        self._llm_client = OllamaClient(settings)
        self._planner = Planner()
        self._validator = Validator()
        self._responder = Responder(settings, self._llm_client)
        self._tool_context = ToolContext(
            settings=settings,
            memory=self._memory,
            scratchpad=self._scratchpad,
        )

    def initialize_state(self, *, force_identity: bool = False) -> dict[str, object]:
        self._settings.soul_home.mkdir(parents=True, exist_ok=True)
        self._memory.ensure_ready()
        self._scratchpad.ensure_ready()
        if force_identity or not self._settings.identity_path.exists():
            self._settings.identity_path.write_text(json.dumps(DEFAULT_IDENTITY, indent=2) + "\n", encoding="utf-8")
            identity_created = True
        else:
            identity_created = False
        return {
            "workspace_root": str(self._settings.workspace_root),
            "soul_home": str(self._settings.soul_home),
            "memory_path": str(self._settings.memory_path),
            "scratchpad_path": str(self._settings.scratchpad_path),
            "identity_path": str(self._settings.identity_path),
            "identity_created": identity_created,
        }

    def doctor(self) -> dict[str, object]:
        self.initialize_state()
        warnings: list[str] = []
        try:
            installed_models = self._llm_client.list_models()
            ollama_available = True
        except RuntimeError as exc:
            warnings.append(str(exc))
            installed_models = []
            ollama_available = False

        required_models = list(
            dict.fromkeys(
                [
                    self._settings.manual_model,
                    self._settings.autonomous_model,
                    self._settings.research_model,
                ]
            )
        )
        return {
            "workspace_root": str(self._settings.workspace_root),
            "soul_home": str(self._settings.soul_home),
            "memory_path": str(self._settings.memory_path),
            "scratchpad_path": str(self._settings.scratchpad_path),
            "identity_path": str(self._settings.identity_path),
            "profile_path": str(self._settings.profile_path),
            "ollama_base_url": self._settings.ollama_base_url,
            "ollama_available": ollama_available,
            "manual_model": self._settings.manual_model,
            "autonomous_model": self._settings.autonomous_model,
            "research_model": self._settings.research_model,
            "installed_models": installed_models,
            "missing_models": [model for model in required_models if model not in installed_models],
            "warnings": warnings,
        }

    def _execute_tool_calls(self, prompt: str, tool_calls: list[object]) -> tuple[list[ToolTrace], list[AgentEvent], list[MemoryEntry]]:
        del prompt
        traces: list[ToolTrace] = []
        events: list[AgentEvent] = []
        memories: list[MemoryEntry] = []

        for tool_call in tool_calls:
            name = getattr(tool_call, "name", "")
            input_data = getattr(tool_call, "input", {})
            try:
                result = self._registry.run(name, self._tool_context, input_data)
            except Exception as exc:  # pylint: disable=broad-except
                event = AgentEvent(kind="tool", title=f"{name} failed", detail=str(exc))
                events.append(event)
                self._scratchpad.append(event)
                continue

            trace = ToolTrace(name=name, summary=result.summary, output=result.output)
            traces.append(trace)
            event = AgentEvent(kind="tool", title=name, detail=result.summary)
            events.append(event)
            self._scratchpad.append(event)

            if name == "memory_recall" and isinstance(result.output, list):
                memories = [
                    MemoryEntry(
                        id=str(item.get("id", "")),
                        kind=str(item.get("kind", "note")),
                        content=str(item.get("content", "")),
                        tags=[str(tag) for tag in item.get("tags", [])],
                        created_at=str(item.get("created_at", "")),
                    )
                    for item in result.output
                    if isinstance(item, dict)
                ]
                memory_event = AgentEvent(
                    kind="memory",
                    title="Memory recall",
                    detail=f"Loaded {len(memories)} memory item(s).",
                )
                events.append(memory_event)
                self._scratchpad.append(memory_event)

            if name == "web_search" and isinstance(result.output, dict):
                hits = result.output.get("hits", [])
                if isinstance(hits, list):
                    for hit in hits[:2]:
                        if not isinstance(hit, dict):
                            continue
                        url = str(hit.get("url", "")).strip()
                        if not url:
                            continue
                        try:
                            fetched = self._registry.run("web_fetch", self._tool_context, {"url": url})
                        except Exception as exc:  # pylint: disable=broad-except
                            fetch_event = AgentEvent(kind="tool", title="web_fetch failed", detail=str(exc))
                            events.append(fetch_event)
                            self._scratchpad.append(fetch_event)
                            continue

                        fetch_trace = ToolTrace(name="web_fetch", summary=fetched.summary, output=fetched.output)
                        traces.append(fetch_trace)
                        fetch_event = AgentEvent(kind="tool", title="web_fetch", detail=fetched.summary)
                        events.append(fetch_event)
                        self._scratchpad.append(fetch_event)

        return traces, events, memories

    def run(self, prompt: str, *, mode: str = "manual", model: str | None = None) -> RunResult:
        normalized = prompt.strip()
        if not normalized:
            raise ValueError("Prompt must not be empty.")

        self.initialize_state()
        plan = self._planner.build_plan(normalized, mode=mode)
        planning_event = AgentEvent(
            kind="planning",
            title="Plan",
            detail=" | ".join(plan.steps),
        )
        self._scratchpad.append(planning_event)

        traces, tool_events, memories = self._execute_tool_calls(normalized, plan.tool_calls)
        validation = self._validator.validate(plan=plan, traces=traces)
        validation_event = AgentEvent(
            kind="validation",
            title="Validation",
            detail="; ".join(validation.reasons) or "No validation notes.",
        )
        self._scratchpad.append(validation_event)

        selected_model, reply = self._responder.respond(
            prompt=normalized,
            mode=mode,
            memories=memories,
            traces=traces,
            validation=validation,
            model_override=model,
        )
        result_event = AgentEvent(kind="result", title="Reply", detail=truncate(reply, 200))
        self._scratchpad.append(result_event)

        identity = load_identity(self._settings)
        agent_name = str(identity.get("name", "Soul")).strip() or "Soul"
        self._memory.add(kind="user_request", content=normalized, tags=[mode])
        self._memory.add(
            kind="assistant_reply",
            content=truncate(f"{agent_name}: {reply}", 1_000),
            tags=[mode],
        )

        return RunResult(
            prompt=normalized,
            mode=mode,  # type: ignore[arg-type]
            model=selected_model,
            reply=reply,
            plan=plan,
            validation=validation,
            memories=memories,
            tools=traces,
            events=[planning_event, *tool_events, validation_event, result_event],
        )
