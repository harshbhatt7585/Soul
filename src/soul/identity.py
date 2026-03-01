from __future__ import annotations

import json

from soul.config import Settings

DEFAULT_IDENTITY: dict[str, object] = {
    "name": "Soul",
    "role": "A personal open-source CLI assistant that runs locally first.",
    "mission": [
        "Help the operator think, research, write, and execute practical next steps.",
        "Stay grounded in the available local tools and memory.",
        "Be concise, useful, and honest about limitations.",
    ],
    "principles": [
        "Prefer concrete next actions over abstract advice.",
        "Do not claim to have executed tools unless the tool output is present.",
        "Use memory when it helps, but do not overfit to stale context.",
    ],
}


def initialize_identity_file(settings: Settings, *, overwrite: bool = False) -> bool:
    settings.soul_home.mkdir(parents=True, exist_ok=True)
    if settings.identity_file.exists() and not overwrite:
        return False
    with settings.identity_file.open("w", encoding="utf-8") as handle:
        json.dump(DEFAULT_IDENTITY, handle, indent=2)
        handle.write("\n")
    return True


def load_identity(settings: Settings) -> dict[str, object]:
    if not settings.identity_file.exists():
        return dict(DEFAULT_IDENTITY)

    try:
        with settings.identity_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_IDENTITY)

    identity = dict(DEFAULT_IDENTITY)
    if isinstance(payload, dict):
        identity.update(payload)
    return identity


def build_system_prompt(identity: dict[str, object], *, mode: str) -> str:
    mission = identity.get("mission", [])
    principles = identity.get("principles", [])
    mission_text = "\n".join(f"- {item}" for item in mission if str(item).strip())
    principles_text = "\n".join(f"- {item}" for item in principles if str(item).strip())
    mode_instruction = (
        "Manual mode: follow the user's request directly and keep the answer actionable."
        if mode == "manual"
        else (
            "Autonomous mode: inspect the current goal and memory, then propose the next "
            "highest-value action without pretending that external work already happened."
        )
    )
    return (
        f"Name: {identity.get('name', 'Soul')}\n"
        f"Role: {identity.get('role', DEFAULT_IDENTITY['role'])}\n\n"
        f"Mission:\n{mission_text}\n\n"
        f"Principles:\n{principles_text}\n\n"
        f"{mode_instruction}\n"
        "You run locally on small models. Be concise, explicit, and realistic.\n"
        "Available capabilities in this build: chat, local memory, web search, page crawl, research summaries.\n"
        "If a capability was not invoked, do not imply it was."
    )
