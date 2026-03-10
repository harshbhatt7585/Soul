/**
 * MemoryManager
 *
 * Maintains the three core OpenClaw memory files:
 *   agents.md  – describes what the agent is and its capabilities
 *   soul.md    – the agent's personality, values, and long-term goals
 *   memory.md  – rolling scratchpad updated after each interaction
 *
 * Also owns the heartbeat timer (default: every 30 minutes) which fires
 * a proactive callback so the agent can take initiative (send messages,
 * do background tasks, update memory, etc.)
 */

import fs from "node:fs/promises";
import path from "node:path";

const DEFAULT_AGENTS_MD = `# Agent Identity
You are a helpful AI assistant connected to WhatsApp.
You can receive messages, hold multi-turn conversations, execute code, and remember context across sessions.
`;

const DEFAULT_SOUL_MD = `# Soul
You are curious, direct, and kind. You value accuracy over speed.
You proactively surface useful information without being asked.
You acknowledge uncertainty rather than confabulating.
`;

const DEFAULT_MEMORY_MD = `# Memory
(No memories recorded yet.)
`;

export class MemoryManager {
  /**
   * @param {object} config
   * @param {string} config.memoryDir        – directory for the three .md files
   * @param {number} config.heartbeatMs      – heartbeat interval (default 30min)
   * @param {Function} config.onHeartbeat    – async () => void, called each tick
   * @param {object} logger
   */
  constructor(config, logger) {
    this.config = config;
    this.logger = logger;
    this.memoryDir = config.memoryDir;
    this.heartbeatMs = config.heartbeatMs ?? 30 * 60 * 1000;
    this.onHeartbeat = config.onHeartbeat ?? null;
    this._heartbeatTimer = null;

    // In-memory cache so repeated reads are cheap
    this._cache = {
      agents: null,
      soul: null,
      memory: null,
    };
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  async init() {
    await fs.mkdir(this.memoryDir, { recursive: true });
    await this._ensureFile("agents.md", DEFAULT_AGENTS_MD);
    await this._ensureFile("soul.md", DEFAULT_SOUL_MD);
    await this._ensureFile("memory.md", DEFAULT_MEMORY_MD);
    await this._loadAll();
    this.logger.info({ memoryDir: this.memoryDir }, "memory manager initialised");
  }

  startHeartbeat() {
    if (this._heartbeatTimer) return;
    this._heartbeatTimer = setInterval(() => this._tick(), this.heartbeatMs);
    this._heartbeatTimer.unref?.();
    this.logger.info({ heartbeatMs: this.heartbeatMs }, "heartbeat started");
  }

  stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }

  // ── Public read API ───────────────────────────────────────────────────────

  getAgentsDoc() {
    return this._cache.agents ?? DEFAULT_AGENTS_MD;
  }

  getSoulDoc() {
    return this._cache.soul ?? DEFAULT_SOUL_MD;
  }

  getMemoryDoc() {
    return this._cache.memory ?? DEFAULT_MEMORY_MD;
  }

  /**
   * Build the full system prompt by combining all three docs.
   * Injected at the top of every LLM call.
   */
  buildSystemPrompt(extra = "") {
    return [
      this.getAgentsDoc(),
      "",
      this.getSoulDoc(),
      "",
      this.getMemoryDoc(),
      extra ? `\n${extra}` : "",
    ]
      .join("\n")
      .trim();
  }

  // ── Public write API ──────────────────────────────────────────────────────

  /**
   * Append a timestamped note to memory.md.
   * The LLM calls this after every interaction to persist important context.
   */
  async appendMemory(note) {
    if (!note?.trim()) return;
    const timestamp = new Date().toISOString();
    const entry = `\n## ${timestamp}\n${note.trim()}\n`;
    const current = await this._read("memory.md");
    const updated = current.replace(DEFAULT_MEMORY_MD.trim(), "").trim() + entry;
    await this._write("memory.md", updated);
    this._cache.memory = updated;
    this.logger.info({ bytes: entry.length }, "memory updated");
  }

  /**
   * Overwrite memory.md entirely (e.g. after a compaction/summarisation pass).
   */
  async setMemory(content) {
    await this._write("memory.md", content);
    this._cache.memory = content;
  }

  async setAgentsDoc(content) {
    await this._write("agents.md", content);
    this._cache.agents = content;
  }

  async setSoulDoc(content) {
    await this._write("soul.md", content);
    this._cache.soul = content;
  }

  // ── Heartbeat ─────────────────────────────────────────────────────────────

  async _tick() {
    this.logger.info("heartbeat tick");
    try {
      await this._loadAll(); // refresh cache in case files were edited externally
      if (typeof this.onHeartbeat === "function") {
        await this.onHeartbeat();
      }
    } catch (error) {
      this.logger.error({ error }, "heartbeat handler failed");
    }
  }

  // ── Internals ─────────────────────────────────────────────────────────────

  async _ensureFile(name, defaultContent) {
    const p = path.join(this.memoryDir, name);
    try {
      await fs.access(p);
    } catch {
      await fs.writeFile(p, defaultContent, "utf8");
      this.logger.info({ file: p }, "initialised memory file with defaults");
    }
  }

  async _loadAll() {
    const [agents, soul, memory] = await Promise.all([
      this._read("agents.md"),
      this._read("soul.md"),
      this._read("memory.md"),
    ]);
    this._cache = { agents, soul, memory };
  }

  async _read(name) {
    try {
      return await fs.readFile(path.join(this.memoryDir, name), "utf8");
    } catch {
      return "";
    }
  }

  async _write(name, content) {
    await fs.writeFile(path.join(this.memoryDir, name), content, "utf8");
  }
}
