import fs from "node:fs/promises";

import makeWASocket, {
  Browsers,
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import P from "pino";
import qrcode from "qrcode-terminal";

import { extractMessageText, isGroupJid, isStatusJid, normalizeSenderJid } from "./message.js";
import { OutboxProcessor } from "./outbox.js";
import { SoulBridge } from "./soul-bridge.js";

export class WhatsAppGateway {
  constructor(config) {
    this.config = config;
    this.logger = P(
      { level: "info" },
      P.multistream([
        { stream: process.stdout },
        { stream: P.destination({ dest: this.config.logFile, mkdir: true, sync: false }) },
      ]),
    );
    this.sock = null;
    this.outboxProcessor = new OutboxProcessor(config, this.logger);
    this.soulBridge = new SoulBridge(config, this.logger);
    this.outboxTimer = null;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.stopped = false;
  }

  async start() {
    this.stopped = false;
    await this._ensureDirs();
    await this._connect();
    this._startOutboxLoop();
  }

  async stop() {
    this.stopped = true;
    if (this.outboxTimer) {
      clearInterval(this.outboxTimer);
      this.outboxTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.sock) {
      try {
        this.sock.end(undefined);
      } catch {
        // best-effort shutdown
      }
      this.sock = null;
    }
  }

  async _ensureDirs() {
    await Promise.all([
      fs.mkdir(this.config.authDir, { recursive: true }),
      fs.mkdir(this.config.logsDir, { recursive: true }),
      this.outboxProcessor.ensureDirs(),
    ]);
  }

  async _connect() {
    if (this.stopped) {
      return;
    }
    const { state, saveCreds } = await useMultiFileAuthState(this.config.authDir);
    const { version, isLatest } = await fetchLatestBaileysVersion().catch((error) => {
      this.logger.warn({ error }, "failed to fetch latest Baileys version, using bundled default");
      return { version: undefined, isLatest: false };
    });
    const sock = makeWASocket({
      auth: state,
      browser: Browsers.macOS("Chrome"),
      logger: this.logger,
      markOnlineOnConnect: false,
      syncFullHistory: false,
      shouldSyncHistoryMessage: () => false,
      ...(version ? { version } : {}),
    });

    if (version) {
      this.logger.info({ version, isLatest }, "using WhatsApp Web version");
    }

    sock.ev.on("creds.update", saveCreds);
    sock.ev.on("connection.update", (update) => this._handleConnectionUpdate(update));
    sock.ev.on("messages.upsert", (event) => this._handleMessages(event));

    this.sock = sock;

    if (this.config.pairingPhone && !state.creds.registered) {
      this._requestPairingCode(sock).catch((error) => {
        this.logger.error({ error }, "failed to request pairing code");
      });
    }
  }

  _startOutboxLoop() {
    if (this.outboxTimer) {
      clearInterval(this.outboxTimer);
    }
    this.outboxTimer = setInterval(() => {
      if (!this.sock) {
        return;
      }
      this.outboxProcessor.drain(this.sock).catch((error) => {
        this.logger.error({ error }, "outbox poll failed");
      });
    }, this.config.outboxPollMs);
  }

  async _handleConnectionUpdate(update) {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      qrcode.generate(qr, { small: true });
      this.logger.info("scan the QR code above to link WhatsApp");
    }

    if (connection === "open") {
      this.reconnectAttempts = 0;
      this.logger.info("WhatsApp gateway connected");
      return;
    }

    if (connection !== "close") {
      return;
    }

    const statusCode = lastDisconnect?.error?.output?.statusCode;
    if (statusCode === DisconnectReason.loggedOut) {
      this.logger.error("WhatsApp session logged out; remove auth files and relink");
      return;
    }
    if (statusCode === DisconnectReason.connectionReplaced) {
      this.logger.error("WhatsApp connection was replaced by another active session; stopping gateway");
      await this.stop();
      return;
    }

    const delayMs = Math.min(1000 * (2 ** this.reconnectAttempts), 30000);
    this.reconnectAttempts += 1;
    this.logger.warn({ statusCode, delayMs }, "WhatsApp connection closed, reconnecting");
    this._scheduleReconnect(delayMs);
  }

  _scheduleReconnect(delayMs) {
    if (this.stopped) {
      return;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.reconnectTimer = setTimeout(() => {
      this._connect().catch((error) => {
        this.logger.error({ error }, "failed to reconnect WhatsApp gateway");
      });
    }, delayMs);
  }

  async _requestPairingCode(sock) {
    if (!this.config.pairingPhone) {
      return;
    }
    const code = await sock.requestPairingCode(this.config.pairingPhone);
    this.logger.info({ code }, "use this pairing code in WhatsApp linked devices");
  }

  async _handleMessages(event) {
    if (event?.type !== "notify" || !Array.isArray(event.messages)) {
      return;
    }

    for (const message of event.messages) {
      await this._handleMessage(message);
    }
  }

  async _handleMessage(message) {
    const jid = normalizeSenderJid(message?.key?.remoteJid || "");
    if (!jid || isStatusJid(jid)) {
      return;
    }
    if (!this.config.allowGroups && isGroupJid(jid)) {
      return;
    }
    if (message?.key?.fromMe && !this.config.allowFromMe) {
      return;
    }
    if (this.config.allowedFrom.length > 0 && !this.config.allowedFrom.includes(jid)) {
      this.logger.info({ jid }, "ignored message from non-allowlisted sender");
      return;
    }

    const text = extractMessageText(message);
    if (!text) {
      return;
    }
    const isFromMe = Boolean(message?.key?.fromMe);

    if (this.config.markRead && message?.key && this.sock) {
      await this.sock.readMessages([message.key]);
    }

    const replyJids = this._getReplyJids(message, jid);
    if (replyJids.length === 0) {
      this.logger.warn({ jid }, "could not determine reply jid for inbound message");
      return;
    }

    this.logger.info(
      { jid, replyJids, text, fromMe: isFromMe },
      "received inbound WhatsApp message",
    );

    if (!this.config.autoReply || !this.sock) {
      return;
    }

    try {
      const reply = await this.soulBridge.handleInbound({
        channel: "whatsapp",
        sender_jid: jid,
        text,
        message_id: message?.key?.id || "",
        push_name: message?.pushName || "",
      });

      const replyText = typeof reply?.reply === "string" ? reply.reply.trim() : "";
      if (!replyText) {
        this.logger.warn({ jid }, "Soul bridge returned no reply text");
        return;
      }

      const sent = [];
      for (const replyJid of replyJids) {
        await this.sock.sendPresenceUpdate("composing", replyJid);
        const result = await this.sock.sendMessage(replyJid, { text: replyText });
        sent.push({
          replyJid,
          messageId: result?.key?.id || "",
        });
      }
      this.logger.info({ jid, replyJids, replyText, sent }, "sent WhatsApp reply");
    } catch (error) {
      this.logger.error({ error, jid }, "failed to handle inbound WhatsApp message");
    }
  }

  _getReplyJids(message, inboundJid) {
    if (!message?.key?.fromMe) {
      return inboundJid ? [inboundJid] : [];
    }
    const ownId = this.sock?.user?.id || "";
    const ownNumber = String(ownId).split(":")[0].replace(/\D+/g, "");
    const targets = [];
    if (ownNumber) {
      targets.push(`${ownNumber}@s.whatsapp.net`);
    }
    if (inboundJid && !targets.includes(inboundJid)) {
      targets.push(inboundJid);
    }
    return targets;
  }
}
