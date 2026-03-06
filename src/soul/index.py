from __future__ import annotations

import argparse
import sys
from pathlib import Path

from soul.agent import SoulAgent
from soul.cli import run_repl
from soul.config import load_agent_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="soul", description="Local CLI assistant.")
    parser.add_argument("prompt", nargs="*", help="One-shot prompt to run.")
    parser.add_argument(
        "--mode",
        choices=["manual", "autonomous", "research"],
        default="manual",
        help="Agent mode.",
    )
    parser.add_argument("--model", help="Override the configured model.")
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Workspace root used to load SOUL.md and local config.",
    )
    return parser


def _prompt_from_args_or_stdin(args: argparse.Namespace) -> str | None:
    if args.prompt:
        return " ".join(args.prompt).strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip() or None
    return None


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        config = load_agent_config(args.workspace)
        agent = SoulAgent(config)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    prompt = _prompt_from_args_or_stdin(args)
    if prompt is None:
        return run_repl(agent, mode=args.mode, model=args.model)

    try:
        result = agent.run(prompt, mode=args.mode, model=args.model)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(result.reply)
    return 0
