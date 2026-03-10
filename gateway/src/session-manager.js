export const DM_POLICY = Object.freeze({
  OPEN: "open",
  ALLOWLIST: "allowlist",
  PAIRING: "pairing",
  DISABLED: "disabled",
});

export class Session {
  constructor({ jid, isGroup }) {
    this.jid = jid;
    this.isGroup = isGroup;
    this.history = [];
    this.pairedAt = null;
    this.lastActivityAt = Date.now();
    this.metadata = {};
  }

  addTurn(role, content) {
    this.history.push({ role, content, ts: Date.now() });
    this.lastActivityAt = Date.now();
    if (this.history.length > 40) {
      this.history = this.history.slice(-40);
    }
  }

  toLLMHistory() {
    return this.history.map(({ role, content }) => ({ role, content }));
  }

  isExpired(ttlMs) {
    return Date.now() - this.lastActivityAt > ttlMs;
  }
}

export class SessionManager {
  constructor(config, logger) {
    this.config = config;
    this.logger = logger;
    this.sessions = new Map();
    this.pairedJids = new Set();
    this._compileMentionPatterns();
    this._startEvictionTimer();
  }

  _compileMentionPatterns() {
    const raw = this.config.mentionPatterns ?? [];
    this._mentionRegexes = raw.map((pattern) => new RegExp(pattern, "i"));
    if (this.config.botName) {
      this._mentionRegexes.push(new RegExp(`\\b${this.config.botName}\\b`, "i"));
    }
  }

  _startEvictionTimer() {
    this._evictionTimer = setInterval(() => {
      const ttlMs = this.config.sessionTtlMs ?? 30 * 60 * 1000;
      for (const [jid, session] of this.sessions) {
        if (session.isExpired(ttlMs)) {
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

  shouldRespond({ senderPhone, senderJid, text, isGroup, quotedMessageFromMe }) {
    if (isGroup) {
      return this._shouldRespondInGroup({ text, quotedMessageFromMe });
    }
    return this._shouldRespondInDm({ senderPhone, senderJid });
  }

  _shouldRespondInGroup({ text, quotedMessageFromMe }) {
    if (quotedMessageFromMe) {
      return true;
    }
    return this._mentionRegexes.some((pattern) => pattern.test(text));
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
        return allowed.some((value) => value === senderJid || value === senderPhone);
      }
      case DM_POLICY.PAIRING:
        return this.pairedJids.has(senderJid) || this.pairedJids.has(senderPhone);
      default:
        this.logger.warn({ policy }, "unknown dmPolicy, defaulting to disabled");
        return false;
    }
  }

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

  stripMention(text) {
    let cleaned = text;
    for (const pattern of this._mentionRegexes) {
      cleaned = cleaned.replace(pattern, "").trim();
    }
    return cleaned || text;
  }
}
