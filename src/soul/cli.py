from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from soul.agents import build_research_agent, build_soul_agent
from soul.config import load_settings
from soul.identity import initialize_identity_file
from soul.llm import OllamaClient
from soul.memory import MemoryStore


def render_markdown_report(summary: str, bullet_points: list[str], sources: list[dict[str, object]]) -> str:
    lines = [summary.strip()]
    if bullet_points:
        lines.append("")
        lines.extend(f"- {point}" for point in bullet_points)
    if sources:
        lines.append("")
        lines.append("Sources:")
        lines.extend(f"- {source['title']} ({source['url']})" for source in sources[:5])
    return "\n".join(line for line in lines if line is not None).strip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soul",
        description="Local-first CLI assistant with memory, research, and Ollama-backed small models.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create local Soul state in .soul/.")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the default identity file if it already exists.",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Inspect configured providers.")
    doctor_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )

    chat_parser = subparsers.add_parser("chat", help="Chat with Soul using a local Ollama model.")
    chat_parser.add_argument("prompt", help="User prompt.")
    chat_parser.add_argument("--mode", choices=("manual", "autonomous"), default="manual")
    chat_parser.add_argument("--model", help="Override the default mode model.")
    chat_parser.add_argument("--context", default="", help="Extra context for this turn.")
    chat_parser.add_argument("--format", choices=("text", "json"), default="text")

    autonomous_parser = subparsers.add_parser(
        "autonomous-checkin",
        help="Run one autonomous planning pass using Soul's memory.",
    )
    autonomous_parser.add_argument("--goal", default="", help="Optional goal for the check-in.")
    autonomous_parser.add_argument("--model", help="Override the default autonomous model.")
    autonomous_parser.add_argument("--format", choices=("text", "json"), default="text")

    remember_parser = subparsers.add_parser("remember", help="Store a memory entry locally.")
    remember_parser.add_argument("text", help="Memory content.")
    remember_parser.add_argument("--kind", default="note", help="Memory kind, for example note or preference.")
    remember_parser.add_argument("--tags", nargs="*", default=[], help="Optional memory tags.")

    research_parser = subparsers.add_parser(
        "research",
        help="Search the web, crawl pages, and synthesize a local research report.",
    )
    research_parser.add_argument("prompt", help="Research prompt or question.")
    research_parser.add_argument("--max-results", type=int, default=5)
    research_parser.add_argument("--max-pages", type=int, default=3)
    research_parser.add_argument("--model", help="Override the default research model.")
    research_parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )

    return parser


def _initialize_local_state(settings_path_root: Path, *, force: bool) -> dict[str, object]:
    settings = load_settings(settings_path_root)
    settings.soul_home.mkdir(parents=True, exist_ok=True)
    memory_store = MemoryStore(settings)
    memory_path = memory_store.ensure_ready()
    identity_created = initialize_identity_file(settings, overwrite=force)
    return {
        "workspace_root": str(settings.workspace_root),
        "soul_home": str(settings.soul_home),
        "memory_file": str(memory_path),
        "identity_file": str(settings.identity_file),
        "identity_created": identity_created,
    }


def _render_doctor(output_format: str) -> int:
    settings = load_settings()
    memory_store = MemoryStore(settings)
    memory_store.ensure_ready()
    client = OllamaClient(settings)
    warnings: list[str] = []
    try:
        installed_models = client.list_models()
        ollama_available = True
    except RuntimeError as exc:
        installed_models = []
        ollama_available = False
        warnings.append(str(exc))

    required_models = list(
        dict.fromkeys(
            [
                settings.manual_model,
                settings.autonomous_model,
                settings.research_model,
            ]
        )
    )
    payload = {
        "workspace_root": str(settings.workspace_root),
        "soul_home": str(settings.soul_home),
        "identity_file": str(settings.identity_file),
        "memory_file": str(settings.memory_file),
        "ollama_base_url": settings.ollama_base_url,
        "ollama_available": ollama_available,
        "manual_model": settings.manual_model,
        "autonomous_model": settings.autonomous_model,
        "research_model": settings.research_model,
        "installed_models": installed_models,
        "missing_models": [model for model in required_models if model not in installed_models],
        "search_provider": "serper" if settings.serper_api_key else "duckduckgo",
        "timeout_seconds": settings.request_timeout_seconds,
        "max_document_bytes": settings.max_document_bytes,
        "max_excerpt_chars": settings.max_excerpt_chars,
        "warnings": warnings,
    }
    if output_format == "json":
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
        if payload["missing_models"]:
            print("recommended_pull_commands:")
            for model in payload["missing_models"]:
                print(f"  ollama pull {model}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        payload = _initialize_local_state(Path.cwd(), force=args.force)
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "doctor":
        return _render_doctor(args.format)

    settings = load_settings()
    if args.command == "remember":
        entry = MemoryStore(settings).add(args.text, kind=args.kind, tags=args.tags)
        print(json.dumps(entry.to_dict(), indent=2))
        return 0

    if args.command == "chat":
        agent = build_soul_agent(settings)
        try:
            reply = agent.chat(
                args.prompt,
                mode=args.mode,
                model=args.model,
                context=args.context,
            )
        except (RuntimeError, ValueError) as exc:
            parser.exit(1, f"{exc}\n")
        if args.format == "json":
            print(json.dumps(reply.to_dict(), indent=2))
        else:
            print(reply.reply)
        return 0

    if args.command == "autonomous-checkin":
        agent = build_soul_agent(settings)
        try:
            reply = agent.autonomous_checkin(goal=args.goal, model=args.model)
        except (RuntimeError, ValueError) as exc:
            parser.exit(1, f"{exc}\n")
        if args.format == "json":
            print(json.dumps(reply.to_dict(), indent=2))
        else:
            print(reply.reply)
        return 0

    if args.command == "research":
        if args.model:
            settings.research_model = args.model
        agent = build_research_agent(settings)
        report = agent.run(
            args.prompt,
            max_results=max(1, args.max_results),
            max_pages=max(1, args.max_pages),
        )
        if args.format == "json":
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(
                render_markdown_report(
                    report.summary,
                    report.bullet_points,
                    [source.to_dict() for source in report.sources],
                )
            )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
