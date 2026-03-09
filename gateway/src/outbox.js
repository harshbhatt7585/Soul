import fs from "node:fs/promises";
import path from "node:path";

function sortJsonFiles(paths) {
  return paths.filter((file) => file.endsWith(".json")).sort();
}

async function readJson(filePath) {
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw);
}

async function writeJson(filePath, payload) {
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
}

async function moveFile(source, destination) {
  await fs.mkdir(path.dirname(destination), { recursive: true });
  await fs.rename(source, destination);
}

export class OutboxProcessor {
  constructor(config, logger) {
    this.config = config;
    this.logger = logger;
    this._running = false;
  }

  async ensureDirs() {
    await Promise.all([
      fs.mkdir(this.config.outboxDir, { recursive: true }),
      fs.mkdir(this.config.sentDir, { recursive: true }),
      fs.mkdir(this.config.failedDir, { recursive: true }),
    ]);
  }

  async drain(sock) {
    if (this._running) {
      return;
    }
    this._running = true;
    try {
      await this.ensureDirs();
      const files = sortJsonFiles(await fs.readdir(this.config.outboxDir));
      for (const fileName of files) {
        const source = path.join(this.config.outboxDir, fileName);
        await this._processFile(sock, source, fileName);
      }
    } finally {
      this._running = false;
    }
  }

  async _processFile(sock, source, fileName) {
    let payload;
    try {
      payload = await readJson(source);
    } catch (error) {
      this.logger.error({ error, fileName }, "failed to read outbound message file");
      await moveFile(source, path.join(this.config.failedDir, fileName));
      return;
    }

    const to = typeof payload?.to === "string" ? payload.to.trim() : "";
    const text = typeof payload?.text === "string" ? payload.text.trim() : "";
    if (!to || !text) {
      this.logger.error({ fileName }, "outbound message missing to/text");
      await moveFile(source, path.join(this.config.failedDir, fileName));
      return;
    }

    try {
      const result = await sock.sendMessage(to, { text });
      await writeJson(path.join(this.config.sentDir, fileName), {
        ...payload,
        sent_at: new Date().toISOString(),
        message_id: result?.key?.id || "",
      });
      await fs.unlink(source);
      this.logger.info({ to, fileName }, "sent outbound WhatsApp message");
    } catch (error) {
      this.logger.error({ error, fileName, to }, "failed to send outbound WhatsApp message");
      await moveFile(source, path.join(this.config.failedDir, fileName));
    }
  }
}
