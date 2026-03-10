# OpenClaw — WhatsApp AI Agent Runtime

A faithful re-implementation of the OpenClaw architecture on top of Baileys + Anthropic.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WhatsApp Gateway Process                  │
│                                                             │
│  Baileys WA socket ──► WhatsAppGateway ──► ControlPlaneClient│
│                                                   │  (WS)   │
└───────────────────────────────────────────────────┼─────────┘
                                                    │ ws://localhost:9090
┌───────────────────────────────────────────────────┼─────────┐
│                    Agent Runtime Process           │         │
│                                                   ▼         │
│  GatewayControlPlane (WS server)                            │
│          │                                                   │
│          ▼                                                   │
│  SessionManager ──► shouldRespond? (dmPolicy / mention)      │
│          │                                                   │
│          ▼                                                   │
│  AgentRuntime ──► Anthropic API                              │
│       │    ▲                                                 │
│       │    └── tool_result ◄── ToolRunner                    │
│       │              ├── run_js    (vm sandbox)              │
│       │              ├── read_file                           │
│       │              ├── write_file                          │
│       │              ├── list_files                          │
│       │              └── append_memory ──► MemoryManager     │
│       │                                       │              │
│       └── final reply ──► WS ──► Gateway     │              │
│                                              ▼              │
│                                    agents.md / soul.md /    │
│                                    memory.md  (on disk)     │
│                                                             │
│  MemoryManager ──► Heartbeat (every 30 min)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Implementation |
|---|---|
| No keyword prefix | Mention regex / reply-to-bot detection in `SessionManager` |
| WS control plane | `GatewayControlPlane` — JSON frame protocol |
| Session isolation | Per-JID `Session` objects with 40-turn rolling history |
| dmPolicy | `open` / `allowlist` / `pairing` / `disabled` |
| Agentic tool loop | `AgentRuntime` — loops until `stop_reason === end_turn` |
| Built-in tools | `run_js`, `read_file`, `write_file`, `list_files`, `append_memory` |
| Memory files | `agents.md`, `soul.md`, `memory.md` — loaded into system prompt |
| Auto memory update | Haiku pass after each turn extracts memorable facts |
| Heartbeat | Configurable interval (default 30 min), fires `onHeartbeat` callback |

---

## Quick Start

### 1. Install dependencies

```bash
npm install @anthropic-ai/sdk @whiskeysockets/baileys pino ws
```

### 2. Set environment variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export DM_POLICY=open               # open | allowlist | pairing | disabled
export BOT_NAME="MyBot"             # used for @mention detection in groups
export MENTION_PATTERNS="@mybot,hey bot"  # comma-separated regex strings
export WS_SECRET=changeme           # shared secret between gateway and runtime
export WS_PORT=9090
export HEARTBEAT_MS=1800000         # 30 minutes
export MEMORY_DIR=./memory
export WORKSPACE_DIR=./workspace
```

### 3. Start the agent runtime

```bash
node main.js
```

### 4. Start the WhatsApp gateway (separate process)

```bash
# Set the gateway to connect to the control plane
export CONTROL_PLANE_URL=ws://localhost:9090
export CONTROL_PLANE_SECRET=changeme
node gateway-process.js   # wraps WhatsAppGateway
```

---

## File Structure

```
openclaw/
├── main.js                        # Agent runtime entry point
├── src/
│   ├── gateway.js                 # WhatsApp gateway (Baileys)
│   ├── gateway-control-plane.js   # WebSocket control plane server
│   ├── session-manager.js         # Per-JID sessions + dmPolicy
│   ├── agent-runtime.js           # Agentic LLM loop
│   ├── tool-runner.js             # Tool execution (run_js, file I/O, memory)
│   └── memory-manager.js          # agents.md / soul.md / memory.md + heartbeat
├── memory/
│   ├── agents.md                  # Agent identity (editable)
│   ├── soul.md                    # Personality & values (editable)
│   └── memory.md                  # Rolling auto-updated memory
└── workspace/                     # Agent's read/write file sandbox
```

---

## DM Policy

| Policy | Behaviour |
|---|---|
| `open` | Any DM is processed |
| `allowlist` | Only JIDs in `ALLOWED_FROM` env var |
| `pairing` | Only JIDs that sent `!pair` command first |
| `disabled` | DMs are ignored entirely |

## Group Activation

Groups are only triggered when:
- The message matches one of the `MENTION_PATTERNS` regexes, **or**
- The message is a direct reply to a message sent by the bot

The bot's mention tokens are stripped from the text before it reaches the LLM.

---

## Customising the Agent

Edit the memory files directly — they are reloaded on every heartbeat:

- **`memory/agents.md`** — what the agent can do, its name, capabilities
- **`memory/soul.md`** — personality, tone, values, rules
- **`memory/memory.md`** — auto-maintained by the LLM; you can also edit manually
