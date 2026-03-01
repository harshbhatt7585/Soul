from __future__ import annotations

import argparse
import json
from typing import Sequence

from soul.agent.orchestrator import SoulOrchestrator
from soul.cli import run_repl
from soul.config import load_settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soul",
        description="Dexter-inspired local CLI assistant scaffold implemented in Python.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create the local .soul state files.")
    init_parser.add_argument("--force-identity", action="store_true", help="Overwrite .soul/identity.json.")

    doctor_parser = subparsers.add_parser("doctor", help="Inspect local paths and Ollama model availability.")
    doctor_parser.add_argument("--format", choices=("text", "json"), default="text")

    run_parser = subparsers.add_parser("run", help="Execute one orchestrated Soul turn.")
    run_parser.add_argument("--prompt", required=True, help="Prompt or task for Soul.")
    run_parser.add_argument("--mode", choices=("manual", "autonomous"), default="manual")
    run_parser.add_argument("--model", help="Override the default model for this run.")
    run_parser.add_argument("--json", action="store_true", help="Render the full run payload as JSON.")

    repl_parser = subparsers.add_parser("repl", help="Open an interactive local REPL.")
    repl_parser.add_argument("--mode", choices=("manual", "autonomous"), default="manual")
    repl_parser.add_argument("--model", help="Override the default model in the REPL.")

    return parser


def _print_text_payload(payload: dict[str, object]) -> None:
    for key, value in payload.items():
        print(f"{key}: {value}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()
    orchestrator = SoulOrchestrator(settings)

    if args.command == "init":
        print(json.dumps(orchestrator.initialize_state(force_identity=args.force_identity), indent=2))
        return 0

    if args.command == "doctor":
        payload = orchestrator.doctor()
        if args.format == "json":
            print(json.dumps(payload, indent=2))
        else:
            _print_text_payload(payload)
            missing = payload.get("missing_models", [])
            if isinstance(missing, list) and missing:
                print("recommended_pull_commands:")
                for model in missing:
                    print(f"  ollama pull {model}")
        return 0

    if args.command == "run":
        result = orchestrator.run(args.prompt, mode=args.mode, model=args.model)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.reply)
        return 0

    if args.command == "repl":
        return run_repl(orchestrator, mode=args.mode, model=args.model)

    parser.error(f"Unknown command: {args.command}")
    return 2
