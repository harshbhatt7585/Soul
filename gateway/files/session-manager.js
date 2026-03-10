/**
 * SessionManager
 *
 * Manages per-JID conversation sessions, DM access policy,
 * and mention/reply-based group activation — mirroring OpenClaw's session model.
 *
 * dmPolicy values:
 *   "open"      – any DM is accepted
 *   "allowlist" – only JIDs in config.allowedFrom may DM
 *   "pairing"   – only JIDs that have been explicitly paired (via !pair command) may DM
 *   "disabled"  – DMs are never handled
 */

export const DM_POLICY = Object.freeze({
  OPEN: "open",
  ALLOWLIST: "allowlist",
  PAIRING: "pairing",
  DISABLED: "disabled",
});

/**
 * A single conversation session for one JID.
 */
export class Session {
  constructor({ jid, isGroup }) {
    this.jid = jid;
    this.isGroup = isGroup;
    this.history = [];          // [{role, content, ts}]
    this.pairedAt = null;       // Date — set when a DM is paired
    this.lastActivityAt = Date.now();
    this.metadata = {};
  }

  addTurn(role, content) {
    this.history.push({ role, content, ts: Date.now() });
    this.lastActivityAt = Date.now();
    // Keep last 40 turns in memory to bound context size
    if (this.history.length > 40) {
      this.history = this.history.slice(-40);
    }
  }

  /** Returns history formatted for the LLM messages array */
  toLLMHistory() {
    return this.history.map(({ role, content }) => ({ role, content }));
  }

  isExpired(ttlMs) {
    return Date.now() - this.lastActivityAt > ttlMs;
  }
}

export class SessionManager {
  /**
   * @param {object} config
   * @param {string} config.dmPolicy          – one of DM_POLICY values
   * @param {string[]} config.allowedFrom      – JIDs/phones for allowlist
   * @param {string[]} config.mentionPatterns  – regex strings that trigger bot in groups
   * @param {string} config.botName            – used for mention matching
   * @param {number} config.sessionTtlMs       – idle TTL before session is evicted
   * @param {object} logger
   */
  constructor(config, logger) {
    this.config = config;
    this.logger = logger;
    this.sessions = new Map();   // jid → Session
    this.pairedJids = new Set(); // for "pairing" dmPolicy

    this._compileMentionPatterns();
    this._startEvictionTimer();
  }

  _compileMentionPatterns() {
    const raw = this.config.mentionPatterns ?? [];
    this._mentionRegexes = raw.map((p) => new RegExp(p, "i"));
    if (this.config.botName) {
      this._mentionRegexes.push(new RegExp(`\\b${this.config.botName}\\b`, "i"));
    }
  }

  /**
   * Evict sessions idle longer than sessionTtlMs every 5 minutes.
   */
  _startEvictionTimer() {
    this._evictionTimer = setInterval(() => {
      const ttl = this.config.sessionTtlMs ?? 30 * 60 * 1000;
      for (const [jid, session] of this.sessions) {
        if (session.isExpired(ttl)) {
          this.sessions.delete(jid);
          this.logger.info({ jid }, "session evicted due to inactivity");
        }
      }
    }, 5 * 60 * 1000);
    this._evictionTimer.unref?.();
  }

  stop() {
    clearInterval(this._evictionTimer);
  }

  getOrCreate(jid, { isGroup }) {
    if (!this.sessions.has(jid)) {
      this.sessions.set(jid, new Session({ jid, isGroup }));
    }
    return this.sessions.get(jid);
  }

  get(jid) {
    return this.sessions.get(jid) ?? null;
  }

  /**
   * Returns true if the bot should respond to this message.
   *
   * Rules:
   *  - Status/broadcast JIDs are always rejected (handled upstream).
   *  - Groups: only respond when the bot is explicitly mentioned or the
   *    message is a direct reply to a bot message.
   *  - DMs: apply dmPolicy.
   */
  shouldRespond({ chatJid, senderPhone, senderJid, text, isGroup, quotedMessageFromMe }) {
    if (isGroup) {
      return this._shouldRespondInGroup({ text, quotedMessageFromMe });
    }
    return this._shouldRespondInDm({ senderPhone, senderJid });
  }

  _shouldRespondInGroup({ text, quotedMessageFromMe }) {
    // Always respond when replying directly to a bot message
    if (quotedMessageFromMe) {
      return true;
    }
    // Respond if text matches any mention pattern
    return this._mentionRegexes.some((re) => re.test(text));
  }

  _shouldRespondInDm({ senderPhone, senderJid }) {
    const policy = this.config.dmPolicy ?? DM_POLICY.OPEN;

    switch (policy) {
      case DM_POLICY.DISABLED:
        return false;

      case DM_POLICY.OPEN:
        return true;

      case DM_POLICY.ALLOWLIST: {
        const allowed = this.config.allowedFrom ?? [];
        return allowed.some((a) => a === senderJid || a === senderPhone);
      }

      case DM_POLICY.PAIRING:
        return this.pairedJids.has(senderJid) || this.pairedJids.has(senderPhone);

      default:
        this.logger.warn({ policy }, "unknown dmPolicy, defaulting to disabled");
        return false;
    }
  }

  /**
   * Register a JID as paired (for "pairing" dmPolicy).
   */
  pair(jid) {
    this.pairedJids.add(jid);
    const session = this.getOrCreate(jid, { isGroup: false });
    session.pairedAt = new Date();
    this.logger.info({ jid }, "DM pairing registered");
  }

  unpair(jid) {
    this.pairedJids.delete(jid);
    this.sessions.delete(jid);
    this.logger.info({ jid }, "DM pairing removed");
  }

  /**
   * Strip the bot's mention from text so the LLM sees a clean prompt.
   */
  stripMention(text) {
    let cleaned = text;
    for (const re of this._mentionRegexes) {
      cleaned = cleaned.replace(re, "").trim();
    }
    return cleaned || text;
  }
}
