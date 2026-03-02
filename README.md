# Soul

Soul is a local-first Python CLI assistant scaffold inspired by the architecture of [Dexter](https://github.com/virattt/dexter), but adapted for personal agents, local memory, and small Ollama models.

Dexter is TypeScript-based, but this repo deliberately translates its architecture into Python:

- `src/soul/index.py`: entrypoint and command routing
- `src/soul/cli.py`: interactive terminal loop
- `src/soul/agent/`: planner, runner, validator, responder, scratchpad, and run types
- `src/soul/models/`: model provider abstraction
- `src/soul/tools/`: tool registry plus web and memory tools
- `src/soul/storage/`: local memory store

The implementation here is original boilerplate, not a source copy. The goal is to preserve Dexter's layering and workflow in a Python-first local project.

## Core idea

Soul has two modes:

1. `manual`: respond to the operator directly
2. `autonomous`: inspect memory, goals, and scratchpad, then suggest or start the next step

This first scaffold is intentionally small:

- local-first Ollama chat
- append-only memory in `.soul/memory.jsonl`
- append-only run scratchpad in `.soul/scratchpad.jsonl`
- simple web search and fetch tools
- an interactive REPL that can grow into a richer terminal agent

## Local setup

```bash
cd /Users/harshbhatt/Projects/soul
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ollama pull llama3.2:1b
ollama pull qwen2.5:0.5b
soul init
soul doctor
```

## Commands

```bash
soul init
soul doctor
soul run --prompt "Draft Soul's next milestone"
soul run --prompt "Research local email tooling" --mode manual --json
soul run --prompt "Keep Soul moving this week" --mode autonomous
soul repl --mode manual
```

## Environment

- `SOUL_OLLAMA_BASE_URL`: Ollama server URL. Default: `http://127.0.0.1:11434`
- `SOUL_MANUAL_MODEL`: manual mode model. Default: `llama3.2:1b`
- `SOUL_AUTONOMOUS_MODEL`: autonomous mode model. Default: `qwen2.5:0.5b`
- `SOUL_RESEARCH_MODEL`: research-heavy prompts model. Default: `llama3.2:1b`
- `SOUL_SEARCH_LIMIT`: max DuckDuckGo results for the search tool
- `SOUL_REQUEST_TIMEOUT_SECONDS`: timeout for Ollama and web requests
- `SOUL_MAX_DOCUMENT_BYTES`: max fetch size for a crawled page
- `SOUL_MAX_EXCERPT_CHARS`: excerpt cap passed into prompts

## Repo layout

```text
src/soul/
  agent/
    planner.py
    prompts.py
    runner.py
    responder.py
    scratchpad.py
    types.py
    validator.py
  models/
    llm.py
  storage/
    memory.py
  tools/
    base.py
    registry.py
    memory_read.py
    memory_write.py
    web_fetch.py
    web_search.py
  utils/
    text.py
  cli.py
  config.py
  index.py
SOUL.md
```

## How it works

1. `src/soul/index.py` parses the CLI command.
2. `init` creates `.soul/identity.json`, `.soul/memory.jsonl`, and `.soul/scratchpad.jsonl`.
3. `run --prompt` creates the runner and executes one agent turn.
4. The runner executes the turn lifecycle:
   - planner: breaks the request into tool steps
   - runner: executes memory and web tools inline
   - validator: decides whether the gathered context is sufficient
   - responder: builds the final prompt and asks Ollama for the reply
5. `SOUL.md` acts like the agent profile and behavior contract.
6. Relevant memories, tool traces, and scratchpad events are merged into the responder prompt.
7. The final user request and assistant reply are written back into local memory so future turns can reuse them.
8. `repl` wraps the same runner in a local interactive shell.

## Architecture note

Dexter's README describes a four-part architecture: planning, action, validation, and answer synthesis. This repo keeps that same separation, but the implementation is plain Python with standard-library HTTP and file storage instead of Bun, Ink, and LangChain.

## What to customize next

1. Replace the heuristic planner with structured tool calling.
2. Add background scheduling for autonomous runs.
3. Add richer tools like email, messaging, or browser automation.
4. Replace keyword memory search with embeddings.
