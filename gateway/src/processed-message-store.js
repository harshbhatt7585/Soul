import fs from "node:fs/promises";
import path from "node:path";

const DEFAULT_TTL_MS = 14 * 24 * 60 * 60 * 1000;
const DEFAULT_MAX_ENTRIES = 5000;

function normalizeSeenAtMs(value) {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;
}

function toEntryList(parsed) {
  if (Array.isArray(parsed)) {
    return parsed;
  }
  if (Array.isArray(parsed?.entries)) {
    return parsed.entries;
  }
  return [];
}

export class ProcessedMessageStore {
  constructor({
    filePath,
    logger,
    ttlMs = DEFAULT_TTL_MS,
    maxEntries = DEFAULT_MAX_ENTRIES,
  } = {}) {
    this.filePath = filePath;
    this.logger = logger;
    this.ttlMs = ttlMs;
    this.maxEntries = maxEntries;
    this.entries = new Map();
    this.loaded = false;
    this.saveQueue = Promise.resolve();
  }

  async load() {
    if (this.loaded || !this.filePath) {
      return;
    }
    this.loaded = true;

    let shouldRewrite = false;
    try {
      const raw = await fs.readFile(this.filePath, "utf-8");
      const parsed = JSON.parse(raw);
      for (const entry of toEntryList(parsed)) {
        if (!entry || typeof entry !== "object") {
          continue;
        }
        const key = typeof entry.key === "string" ? entry.key.trim() : "";
        const seenAtMs = normalizeSeenAtMs(entry.seenAtMs);
        if (!key || !seenAtMs) {
          shouldRewrite = true;
          continue;
        }
        this.entries.set(key, seenAtMs);
      }
    } catch (error) {
      if (error?.code !== "ENOENT") {
        this.logger?.warn?.(
          { error: String(error), filePath: this.filePath },
          "failed to load processed WhatsApp message store",
        );
      }
    }

    if (this._prune(Date.now())) {
      shouldRewrite = true;
    }
    if (shouldRewrite) {
      await this._enqueueSave();
    }
  }

  has(key, nowMs = Date.now()) {
    if (!key) {
      return false;
    }
    this._prune(nowMs);
    return this.entries.has(key);
  }

  async mark(key, nowMs = Date.now()) {
    if (!key) {
      return;
    }
    this._prune(nowMs);
    this.entries.delete(key);
    this.entries.set(key, nowMs);
    this._trimToLimit();
    await this._enqueueSave();
  }

  async close() {
    await this.saveQueue.catch(() => {});
  }

  _prune(nowMs) {
    let changed = false;
    if (this.ttlMs > 0) {
      for (const [key, seenAtMs] of this.entries) {
        if (!seenAtMs || nowMs - seenAtMs > this.ttlMs) {
          this.entries.delete(key);
          changed = true;
        }
      }
    }
    if (this._trimToLimit()) {
      changed = true;
    }
    return changed;
  }

  _trimToLimit() {
    let changed = false;
    while (this.entries.size > this.maxEntries) {
      const oldestKey = this.entries.keys().next().value;
      if (!oldestKey) {
        break;
      }
      this.entries.delete(oldestKey);
      changed = true;
    }
    return changed;
  }

  async _enqueueSave() {
    this.saveQueue = this.saveQueue
      .catch(() => {})
      .then(() => this._save());
    return this.saveQueue;
  }

  async _save() {
    if (!this.filePath) {
      return;
    }
    await fs.mkdir(path.dirname(this.filePath), { recursive: true });
    const payload = {
      version: 1,
      entries: Array.from(this.entries, ([key, seenAtMs]) => ({ key, seenAtMs })),
    };
    await fs.writeFile(this.filePath, JSON.stringify(payload), "utf-8");
  }
}
