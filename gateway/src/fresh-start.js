import fs from "node:fs/promises";
import path from "node:path";

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

  await removeChildren(config.outboxDir, () => true, logger, "outbox");
  await removeChildren(config.sentDir, () => true, logger, "sent");
  await removeChildren(config.failedDir, () => true, logger, "failed");
}
