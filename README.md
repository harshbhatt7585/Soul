# Soul

Soul is a local-first open-source CLI assistant with memory, identity, and two operating modes:

1. `manual`: you give context and direct instructions.
2. `autonomous`: Soul checks in on its own goal state and proposes the next useful step.

The current first step is intentionally small:

- a simple local agent backed by Ollama
- lightweight memory stored on disk
- web search and page crawling
- deep-research style synthesis over fetched pages

This repo now defaults to small local models:

- `llama3.2:1b` for manual chat and research
- `qwen2.5:0.5b` for autonomous check-ins

## Local setup

```bash
cd /Users/harshbhatt/Projects/soul
cp .env.example .env
ollama pull llama3.2:1b
ollama pull qwen2.5:0.5b
uv run soul init
uv run soul doctor
```

If you prefer not to install the CLI entry point yet, use:

```bash
PYTHONPATH=src python -m soul doctor
```

## Commands

```bash
uv run soul init
uv run soul doctor
uv run soul chat "Draft a short plan for Soul" --mode manual
uv run soul autonomous-checkin --goal "Keep the project moving each morning"
uv run soul remember "I prefer concise answers" --kind preference
uv run soul research "best open-source email APIs for small products" --format markdown
```

## What `init` creates

- `.soul/identity.json`: editable identity and behavior config
- `.soul/memory.jsonl`: append-only local memory store

## Environment

- `SOUL_OLLAMA_BASE_URL`: Ollama server URL. Default: `http://127.0.0.1:11434`
- `SOUL_MANUAL_MODEL`: default manual model. Default: `llama3.2:1b`
- `SOUL_AUTONOMOUS_MODEL`: default autonomous model. Default: `qwen2.5:0.5b`
- `SOUL_RESEARCH_MODEL`: default research model. Default: `llama3.2:1b`
- `SOUL_REQUEST_TIMEOUT_SECONDS`: timeout for Ollama and web requests
- `SOUL_MAX_DOCUMENT_BYTES`: fetch limit for crawled pages
- `SOUL_MAX_EXCERPT_CHARS`: max source excerpt length in research summaries

## Project layout

```text
src/soul/cli.py             CLI entrypoint
src/soul/agents/core.py     Manual and autonomous agent flows
src/soul/agents/research.py Research orchestration
src/soul/memory.py          File-based local memory
src/soul/identity.py        Soul identity loader and prompt builder
src/soul/llm.py             Ollama client and local synthesis
src/soul/tools/             Search, fetch, and scraping helpers
```

## Next steps

1. Add true tool-calling so `chat` can invoke search and crawl directly.
2. Add scheduled autonomous runs with a lockfile and task queue.
3. Replace keyword memory search with embeddings when the local stack is ready.
