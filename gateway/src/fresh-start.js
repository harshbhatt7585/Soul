import fs from "node:fs/promises";
import path from "node:path";

const AUTH_KEEP_FILES = new Set(["creds.json", "creds.backup.json"]);
const AUTH_KEEP_PREFIXES = ["app-state-sync-key-", "pre-key-"];

function shouldKeepAuthFile(name) {
  if (AUTH_KEEP_FILES.has(name)) {
    return true;
  }
  return AUTH_KEEP_PREFIXES.some((prefix) => name.startsWith(prefix));
}

async function removeChildren(dirPath, predicate, logger, scope) {
  let entries = [];
  try {
    entries = await fs.readdir(dirPath, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    const targetPath = path.join(dirPath, entry.name);
    if (!predicate(entry)) {
      continue;
    }
    try {
      await fs.rm(targetPath, { recursive: true, force: true });
      logger.info({ scope, path: targetPath }, "removed stale gateway state");
    } catch (error) {
      logger.warn({ scope, path: targetPath, error: String(error) }, "failed removing stale gateway state");
    }
  }
}

export async function prepareFreshStart(config, logger) {
  if (!config.freshStartOnBoot) {
    return;
  }

  if (config.clearAuthSessionsOnBoot) {
    await removeChildren(
      config.authDir,
      (entry) => entry.isFile() && !shouldKeepAuthFile(entry.name),
      logger,
      "auth",
    );
  }
  await removeChildren(config.outboxDir, () => true, logger, "outbox");
  await removeChildren(config.sentDir, () => true, logger, "sent");
  await removeChildren(config.failedDir, () => true, logger, "failed");
}
