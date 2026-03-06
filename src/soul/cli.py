from __future__ import annotations

import json

from soul.agent.agent import SoulAgent
from soul.agent.types import RunResult


def print_run_events(result: RunResult) -> None:
    if not result.events:
        return

    for event in result.events:
        print(f"[{event.kind}] {event.title}")
        try:
            payload = json.loads(event.detail)
        except json.JSONDecodeError:
            print(event.detail)
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=True))


# TODO: Support one-shot prompts and stdin piping in addition to the interactive REPL loop.
# TODO: Stream planning and tool events to the terminal once the agent exposes structured progress updates.
def run_repl(agent: SoulAgent, *, model: str | None = None) -> int:
    print("Soul REPL")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        try:
            prompt = input("> ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break

        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            break

        try:
            result = agent.run(prompt, model=model)
        except Exception as exc:  # pylint: disable=broad-except
            # TODO: Map expected runtime failures to clearer user-facing messages and exit codes.
            print(f"Error: {exc}")
            continue

        print_run_events(result)
        print(result.reply)
        print()

    return 0
