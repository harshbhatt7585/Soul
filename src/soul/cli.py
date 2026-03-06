from __future__ import annotations

from soul.agent.agent import SoulAgent


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

        print(result.reply)
        print()

    return 0
