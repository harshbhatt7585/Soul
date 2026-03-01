from __future__ import annotations

from soul.config import Settings
from soul.identity import build_system_prompt, load_identity
from soul.llm import OllamaClient
from soul.memory import MemoryStore
from soul.models import AgentMode, AssistantReply, ChatMessage, utc_now_iso


class SoulAgent:
    def __init__(
        self,
        *,
        settings: Settings,
        llm_client: OllamaClient,
        memory_store: MemoryStore,
    ) -> None:
        self._settings = settings
        self._llm_client = llm_client
        self._memory_store = memory_store

    def _model_for_mode(self, mode: AgentMode, override: str | None) -> str:
        if override:
            return override
        if mode == "autonomous":
            return self._settings.autonomous_model
        return self._settings.manual_model

    def chat(
        self,
        prompt: str,
        *,
        mode: AgentMode = "manual",
        model: str | None = None,
        context: str = "",
    ) -> AssistantReply:
        normalized = prompt.strip()
        if not normalized:
            raise ValueError("Prompt must not be empty.")

        identity = load_identity(self._settings)
        memories = self._memory_store.search(normalized, limit=4)
        system_prompt = build_system_prompt(identity, mode=mode)
        sections = []
        if context.strip():
            sections.append(f"Additional context:\n{context.strip()}")
        if memories:
            memory_lines = [
                f"- [{memory.kind}] {memory.content}"
                for memory in memories
            ]
            sections.append("Relevant memory:\n" + "\n".join(memory_lines))
        sections.append(f"Task:\n{normalized}")
        selected_model = self._model_for_mode(mode, model)
        reply = self._llm_client.chat(
            model=selected_model,
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content="\n\n".join(sections)),
            ],
        )

        self._memory_store.add(normalized, kind="user_request", tags=[mode])
        self._memory_store.add(reply.content[:1000], kind="assistant_reply", tags=[mode])

        return AssistantReply(
            prompt=normalized,
            mode=mode,
            model=reply.model,
            reply=reply.content,
            created_at=utc_now_iso(),
            memories=memories,
        )

    def autonomous_checkin(self, *, goal: str = "", model: str | None = None) -> AssistantReply:
        prompt = goal.strip() or "Review the current memory and propose the next useful action."
        context = (
            "Return a short response with: current focus, one next action, and one blocker or risk. "
            "Do not pretend that tools already ran."
        )
        return self.chat(prompt, mode="autonomous", model=model, context=context)


def build_soul_agent(settings: Settings) -> SoulAgent:
    memory_store = MemoryStore(settings)
    memory_store.ensure_ready()
    return SoulAgent(
        settings=settings,
        llm_client=OllamaClient(settings),
        memory_store=memory_store,
    )
