from __future__ import annotations

from soul.agent.orchestrator import SoulOrchestrator


def run_repl(orchestrator: SoulOrchestrator, *, mode: str = "manual", model: str | None = None) -> int:
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
            result = orchestrator.run(prompt, mode=mode, model=model)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"Error: {exc}")
            continue

        print(result.reply)
        print()

    return 0
