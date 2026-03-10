/**
 * main.js — OpenClaw-style agent entry point
 *
 * Instantiation order:
 *   1. MemoryManager  — loads agents.md / soul.md / memory.md
 *   2. ToolRunner     — tool execution sandbox
 *   3. AgentRuntime   — agentic LLM loop
 *   4. SessionManager — per-JID session & dmPolicy
 *   5. GatewayControlPlane — WebSocket server
 *   6. WhatsAppGateway — Baileys WA connection (optional, can run separately)
 *
 * The WhatsApp gateway and the agent runtime are intentionally decoupled
 * via the WebSocket control plane so they can run as separate processes.
 */

import { MemoryManager } from "./src/memory-manager.js";
import { ToolRunner } from "./src/tool-runner.js";
import { AgentRuntime } from "./src/agent-runtime.js";
import { SessionManager, DM_POLICY } from "./src/session-manager.js";
import { GatewayControlPlane } from "./src/gateway-control-plane.js";
import P from "pino";

// ── Config ────────────────────────────────────────────────────────────────

const config = {
  // Anthropic model
  model: process.env.ANTHROPIC_MODEL ?? "claude-opus-4-5",
  maxTokens: Number(process.env.MAX_TOKENS ?? 2048),

  // Memory
  memoryDir: process.env.MEMORY_DIR ?? "./memory",

  // Agent workspace (files the LLM can read/write)
  workspaceDir: process.env.WORKSPACE_DIR ?? "./workspace",

  // Session management
  dmPolicy: process.env.DM_POLICY ?? DM_POLICY.OPEN,
  allowedFrom: (process.env.ALLOWED_FROM ?? "").split(",").map((s) => s.trim()).filter(Boolean),
  mentionPatterns: (process.env.MENTION_PATTERNS ?? "").split(",").map((s) => s.trim()).filter(Boolean),
  botName: process.env.BOT_NAME ?? "Assistant",
  sessionTtlMs: Number(process.env.SESSION_TTL_MS ?? 30 * 60 * 1000),

  // Heartbeat
  heartbeatMs: Number(process.env.HEARTBEAT_MS ?? 30 * 60 * 1000),

  // Gateway control plane WebSocket
  wsPort: Number(process.env.WS_PORT ?? 9090),
  wsSecret: process.env.WS_SECRET ?? "",
};

// ── Logger ────────────────────────────────────────────────────────────────

const logger = P({ level: process.env.LOG_LEVEL ?? "info" });

// ── Bootstrap ─────────────────────────────────────────────────────────────

async function main() {
  logger.info("Starting OpenClaw agent runtime…");

  // 1. Memory
  const memoryManager = new MemoryManager(
    {
      memoryDir: config.memoryDir,
      heartbeatMs: config.heartbeatMs,
      onHeartbeat: async () => {
        // Heartbeat hook — e.g. broadcast a proactive message, summarise memory, etc.
        logger.info("Heartbeat: checking if proactive message is needed");
        // controlPlane.broadcast({ type: "proactive", text: "…" }); // example
      },
    },
    logger,
  );
  await memoryManager.init();

  // 2. Tools
  const toolRunner = new ToolRunner(
    { workspaceDir: config.workspaceDir },
    memoryManager,
    logger,
  );

  // 3. Agent runtime
  const agentRuntime = new AgentRuntime(
    { model: config.model, maxTokens: config.maxTokens },
    memoryManager,
    toolRunner,
    logger,
  );

  // 4. Session manager
  const sessionManager = new SessionManager(
    {
      dmPolicy: config.dmPolicy,
      allowedFrom: config.allowedFrom,
      mentionPatterns: config.mentionPatterns,
      botName: config.botName,
      sessionTtlMs: config.sessionTtlMs,
    },
    logger,
  );

  // 5. Control plane WebSocket server
  const controlPlane = new GatewayControlPlane(
    { wsPort: config.wsPort, wsSecret: config.wsSecret },
    sessionManager,
    agentRuntime,
    logger,
  );
  controlPlane.start();

  // 6. Start heartbeat (after control plane is up so it can broadcast)
  memoryManager.config.onHeartbeat = async () => {
    logger.info("Heartbeat tick — agent is alive");
    // Example: summarise memory if it's grown large
    const mem = memoryManager.getMemoryDoc();
    if (mem.length > 50_000) {
      logger.info("Memory doc large — summarisation pass could run here");
    }
  };
  memoryManager.startHeartbeat();

  // ── Graceful shutdown ─────────────────────────────────────────────────
  const shutdown = async (signal) => {
    logger.info({ signal }, "Shutting down…");
    memoryManager.stopHeartbeat();
    sessionManager.stop();
    controlPlane.stop();
    process.exit(0);
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));

  logger.info(
    {
      wsPort: config.wsPort,
      dmPolicy: config.dmPolicy,
      model: config.model,
      heartbeatMs: config.heartbeatMs,
    },
    "OpenClaw agent runtime started",
  );
}

main().catch((err) => {
  logger.error({ err }, "Fatal startup error");
  process.exit(1);
});
