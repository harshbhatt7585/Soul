from __future__ import annotations

from typing import Any


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_valid_plan(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False

    todo = payload.get("todo")
    reasoning = payload.get("reasoning")
    notes = payload.get("notes", "")

    if not isinstance(todo, list):
        return False
    if not all(_is_non_empty_string(item) for item in todo):
        return False
    if not _is_non_empty_string(reasoning):
        return False
    if not isinstance(notes, str):
        return False

    forbidden_keys = {"text", "ok", "tool_calls"}
    return not any(key in payload for key in forbidden_keys)


def is_valid_response(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False

    text = payload.get("text")
    reasoning = payload.get("reasoning")
    if not _is_non_empty_string(text):
        return False
    if not isinstance(reasoning, str):
        return False

    forbidden_keys = {"todo", "ok", "tool_calls"}
    return not any(key in payload for key in forbidden_keys)


def is_valid_verification(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False

    ok = payload.get("ok")
    reasoning = payload.get("reasoning")
    feedback = payload.get("feedback")

    if not isinstance(ok, bool):
        return False
    if not _is_non_empty_string(reasoning):
        return False
    if not isinstance(feedback, str):
        return False
    if ok and feedback.strip():
        return False

    forbidden_keys = {"todo", "text", "tool_calls"}
    return not any(key in payload for key in forbidden_keys)


def is_valid_tool_identification_payload(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False

    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list):
        return False
    return all(isinstance(item, dict) for item in tool_calls)


__all__ = [
    "is_valid_plan",
    "is_valid_response",
    "is_valid_tool_identification_payload",
    "is_valid_verification",
]
