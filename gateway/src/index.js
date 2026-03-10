import P from "pino";

import { AgentRuntime } from "./agent-runtime.js";
import { loadConfig } from "./config.js";
import { prepareFreshStart } from "./fresh-start.js";
import { GatewayControlPlane } from "./gateway-control-plane.js";
import { ProcessLock } from "./process-lock.js";
import { SessionManager } from "./session-manager.js";
import { WhatsAppGateway } from "./whatsapp-gateway.js";

async function main() {
  const config = loadConfig();
  const logger = P({ level: process.env.LOG_LEVEL ?? "info" });
  const lock = new ProcessLock(config.lockFile);
  await lock.acquire();
  await prepareFreshStart(config, logger);

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
  const agentRuntime = new AgentRuntime(config, logger);
  const controlPlane = new GatewayControlPlane(
    { wsPort: config.wsPort, wsSecret: config.wsSecret },
    sessionManager,
    agentRuntime,
    logger,
  );
  controlPlane.start();

  const gateway = new WhatsAppGateway(config);

  let shuttingDown = false;
  const shutdown = async (exitCode = 0) => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    try {
      await gateway.stop();
    } finally {
      sessionManager.stop();
      controlPlane.stop();
      await lock.release();
    }
    process.exitCode = exitCode;
  };

  process.on("SIGINT", () => {
    void shutdown(0);
  });
  process.on("SIGTERM", () => {
    void shutdown(0);
  });
  process.on("SIGHUP", () => {
    void shutdown(0);
  });
  process.on("exit", () => {
    lock.releaseSync();
  });

  await gateway.start();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
