import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

function isProcessAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error?.code === "EPERM";
  }
}

async function readLock(filePath) {
  try {
    const raw = await fsp.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export class ProcessLock {
  constructor(filePath) {
    this.filePath = filePath;
    this.acquired = false;
  }

  async acquire() {
    await fsp.mkdir(path.dirname(this.filePath), { recursive: true });
    const payload = `${JSON.stringify({
      pid: process.pid,
      started_at: new Date().toISOString(),
    })}\n`;

    try {
      await fsp.writeFile(this.filePath, payload, { flag: "wx", encoding: "utf-8" });
      this.acquired = true;
      return;
    } catch (error) {
      if (error?.code !== "EEXIST") {
        throw error;
      }
    }

    const existing = await readLock(this.filePath);
    if (existing?.pid && isProcessAlive(existing.pid)) {
      throw new Error(`Another Soul WhatsApp gateway is already running (pid ${existing.pid}).`);
    }

    await fsp.rm(this.filePath, { force: true });
    await fsp.writeFile(this.filePath, payload, { flag: "wx", encoding: "utf-8" });
    this.acquired = true;
  }

  async release() {
    if (!this.acquired) {
      return;
    }
    this.acquired = false;
    await fsp.rm(this.filePath, { force: true });
  }

  releaseSync() {
    if (!this.acquired) {
      return;
    }
    this.acquired = false;
    try {
      fs.rmSync(this.filePath, { force: true });
    } catch {
      // best-effort cleanup
    }
  }
}
