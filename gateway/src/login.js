import P from "pino";

import { loadConfig } from "./config.js";
import { createWaSocket, formatError, getStatusCode, waitForWaConnection } from "./session.js";
import { DisconnectReason } from "@whiskeysockets/baileys";

async function main() {
  const config = loadConfig();
  const logger = P({ level: "info" });
  const { sock } = await createWaSocket({
    authDir: config.authDir,
    logger,
    printQr: true,
  });

  console.log("Waiting for WhatsApp connection...");
  try {
    await waitForWaConnection(sock);
    console.log("Linked. Credentials saved for future gateway runs.");
  } catch (error) {
    const statusCode = getStatusCode(error?.error) ?? getStatusCode(error);
    if (statusCode === 515) {
      console.log("WhatsApp requested a restart after pairing; reconnecting once...");
      try {
        sock.ws?.close();
      } catch {
        // best-effort close
      }
      const { sock: retrySock } = await createWaSocket({
        authDir: config.authDir,
        logger,
        printQr: false,
      });
      try {
        await waitForWaConnection(retrySock);
        console.log("Linked after restart. Web session is ready.");
        return;
      } finally {
        setTimeout(() => {
          try {
            retrySock.ws?.close();
          } catch {
            // best-effort close
          }
        }, 500);
      }
    }

    if (statusCode === DisconnectReason.loggedOut) {
      console.error("WhatsApp reported the session is logged out. Clear auth and run login again.");
      throw new Error("Session logged out; rerun login.", { cause: error });
    }

    throw new Error(`WhatsApp Web connection ended before opening. ${formatError(error)}`, { cause: error });
  } finally {
    setTimeout(() => {
      try {
        sock.ws?.close();
      } catch {
        // best-effort close
      }
    }, 500);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
