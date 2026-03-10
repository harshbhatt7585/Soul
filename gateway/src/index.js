import { loadConfig } from "./config.js";
import { ProcessLock } from "./process-lock.js";
import { WhatsAppGateway } from "./whatsapp-gateway.js";

async function main() {
  const config = loadConfig();
  const lock = new ProcessLock(config.lockFile);
  await lock.acquire();
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
