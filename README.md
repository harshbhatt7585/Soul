# Soul

Soul is a local-first Python CLI assistant with:

- planning and tool use
- file-based local memory
- web search for live information
- an optional WhatsApp Web gateway

## Core Agent

Current agent flow:

```text
User Prompt
  -> Planning
  -> Tool selection
  -> Tool execution
  -> Final response
```

Current tools:

1. `memory_recall`
2. `memory_write`
3. `web_search`
4. `web_fetch`
5. `html_praser`

## WhatsApp Gateway

The repository includes a clean OpenClaw-style WhatsApp gateway under `gateway/README.md`.

Architecture:

```text
WhatsApp Web (Baileys)
  -> gateway daemon
  -> Soul bridge
  -> Soul agent

cron / scheduled jobs
  -> queue outbound WhatsApp messages
  -> gateway daemon sends them
```

That split keeps:

- WhatsApp session state in the gateway
- Soul as the agent runtime
- scheduled outbound updates decoupled through an outbox queue
