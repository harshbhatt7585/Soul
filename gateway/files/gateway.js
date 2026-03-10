/**
 * WhatsAppGateway  (revised)
 *
 * Changes from original:
 *  1. No "SOUL:" keyword prefix required — activation is handled by
 *     SessionManager (mention in groups, dmPolicy for DMs).
 *  2. Routes inbound messages to the GatewayControlPlane via WebSocket
 *     rather than calling SoulBridge directly.
 *  3. The WS server reply frame is consumed and sent back over WhatsApp.
 *  4. DM pairing command (!pair / !unpair) is handled inline.
 */

import fs from "node:fs/promises";
import { DisconnectReason } from "@whiskeysockets/baileys";
import P from "pino";
import WebSocket from "ws";

import {
  extractMessageText,
  isGroupJid,
  isStatusJid,
  normalizeSenderJid,
} from "./message.js";
import { OutboxProcessor } from "./outbox.js";
import { ProcessedMessageStore } from "./processed-message-store.js";
import { createWaSocket, formatError, getStatusCode } from "./session.js";

function parseTimestampMs(value) {
  if (value == null) return 0;
  if (typeof value === "number") return value > 1_000_000_000_000 ? value : value * 1000;
  if (typeof value === "bigint") return Number(value > 1_000_000_000_000n ? value : value * 1000n);
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parseTimestampMs(parsed) : 0;
  }
  if (typeof value === "object" && value !== null) {
    if (typeof value.low === "number") return parseTimestampMs(value.low);
    if (typeof value.toNumber === "function") return parseTimestampMs(value.toNumber());
  }
  return 0;
}

function jidToPhone(jid) {
  if (!jid) return "";
  const user = String(jid).trim().split("@")[0] ?? "";
  return user.split(":")[0].replace(/\D+/g, "");
}

function buildHandledMessageKey(message, chatJid) {
  const messageId = typeof message?.key?.id === "string" ? message.key.id.trim() : "";
  if (!chatJid || !messageId) return "";
  const participant = normalizeSenderJid(message?.key?.participant ?? "");
  const fromMe = message?.key?.fromMe ? "me" : "them";
  return [chatJid, participant || "-", fromMe, messageId].join("|");
}

// ── WS client to GatewayControlPlane ─────────────────────────────────────

class ControlPlaneClient {
  constructor({ wsUrl, wsSecret, logger, onReply, onError }) {
    this.wsUrl = wsUrl;
    this.wsSecret = wsSecret;
    this.logger = logger;
    this.onReply = onReply;
    this.onError = onError;
    this.ws = null;
    this.ready = false;
    this._pending = new Map(); // message_id → { resolve, reject }
    this._reconnectTimer = null;
  }

  connect() {
    this.ws = new WebSocket(this.wsUrl);

    this.ws.on("open", () => {
      if (this.wsSecret) {
        this.ws.send(JSON.stringify({ type: "auth", secret: this.wsSecret }));
      }
    });

    this.ws.on("message", (raw) => {
      let frame;
      try { frame = JSON.parse(raw.toString()); } catch { return; }

      if (frame.type === "auth_ok") {
        this.ready = true;
        this.logger.info("Connected to gateway control plane");
        return;
      }
      if (frame.type === "pong") return;

      if (frame.type === "reply" && frame.message_id) {
        const pending = this._pending.get(frame.message_id);
        if (pending) {
          this._pending.delete(frame.message_id);
          pending.resolve(frame.text ?? "");
        }
        this.onReply?.(frame);
        return;
      }

      if (frame.type === "error" && frame.message_id) {
        const pending = this._pending.get(frame.message_id);
        if (pending) {
          this._pending.delete(frame.message_id);
          pending.reject(new Error(frame.error));
        }
        this.onError?.(frame);
      }
    });

    this.ws.on("close", () => {
      this.ready = false;
      this.logger.warn("Control plane connection closed, reconnecting in 5s");
      this._reconnectTimer = setTimeout(() => this.connect(), 5000);
    });

    this.ws.on("error", (err) => {
      this.logger.error({ err }, "Control plane WS error");
    });
  }

  disconnect() {
    clearTimeout(this._reconnectTimer);
    this.ws?.close();
  }

  /**
   * Send an inbound frame and await the reply (or error) from the control plane.
   * Resolves with the reply text string.
   */
  sendInbound(frame) {
    return new Promise((resolve, reject) => {
      if (!this.ready || !this.ws) {
        return reject(new Error("Control plane not connected"));
      }
      const timeout = setTimeout(() => {
        this._pending.delete(frame.message_id);
        reject(new Error("Control plane reply timeout"));
      }, 120_000);

      this._pending.set(frame.message_id, {
        resolve: (text) => { clearTimeout(timeout); resolve(text); },
        reject: (err)  => { clearTimeout(timeout); reject(err);   },
      });

      this.ws.send(JSON.stringify({ type: "inbound", ...frame }));
    });
  }
}

// ── WhatsAppGateway ───────────────────────────────────────────────────────

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
    this.outboxTimer = null;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.connectedAtMs = 0;
    this.processingMessageKeys = new Set();
    this.processedMessageStore = new ProcessedMessageStore({
      filePath: this.config.processedMessagesFile,
      logger: this.logger,
      ttlMs: this.config.processedMessagesTtlMs,
      maxEntries: this.config.processedMessagesMaxEntries,
    });
    this.stopped = false;

    // WS client to control plane
    this.controlPlane = new ControlPlaneClient({
      wsUrl: this.config.controlPlaneUrl ?? "ws://localhost:9090",
      wsSecret: this.config.controlPlaneSecret ?? "",
      logger: this.logger,
    });
  }

  async start() {
    this.stopped = false;
    await this._ensureDirs();
    await this.processedMessageStore.load();
    this.controlPlane.connect();
    await this._connect();
    this._startOutboxLoop();
  }

  async stop() {
    this.stopped = true;
    clearInterval(this.outboxTimer);
    this.outboxTimer = null;
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.controlPlane.disconnect();
    try { this.sock?.ws?.close(); } catch { /* best-effort */ }
    this.sock = null;
    this.connectedAtMs = 0;
    this.processingMessageKeys.clear();
    await this.processedMessageStore.close();
  }

  async _ensureDirs() {
    await Promise.all([
      fs.mkdir(this.config.authDir, { recursive: true }),
      fs.mkdir(this.config.logsDir, { recursive: true }),
      this.outboxProcessor.ensureDirs(),
    ]);
  }

  async _connect() {
    if (this.stopped) return;
    const { sock } = await createWaSocket({
      authDir: this.config.authDir,
      logger: this.logger,
      printQr: false,
    });
    sock.ev.on("connection.update", (u) => this._handleConnectionUpdate(u));
    sock.ev.on("messages.upsert", (e) => this._handleMessages(e));
    this.sock = sock;
  }

  _startOutboxLoop() {
    clearInterval(this.outboxTimer);
    this.outboxTimer = setInterval(() => {
      if (!this.sock) return;
      this.outboxProcessor.drain(this.sock).catch((err) => {
        this.logger.error({ err }, "outbox poll failed");
      });
    }, this.config.outboxPollMs);
  }

  async _handleConnectionUpdate({ connection, lastDisconnect }) {
    if (connection === "open") {
      this.reconnectAttempts = 0;
      this.connectedAtMs = Date.now();
      this.logger.info("WhatsApp gateway connected");
      return;
    }
    if (connection !== "close") return;

    const statusCode = getStatusCode(lastDisconnect?.error);
    if (statusCode === DisconnectReason.loggedOut) {
      this.logger.error("WhatsApp session logged out; re-run the login flow");
      return;
    }
    if (statusCode === DisconnectReason.connectionReplaced) {
      this.logger.error("Session replaced; stopping gateway");
      await this.stop();
      return;
    }

    const delayMs = Math.min(1000 * 2 ** this.reconnectAttempts, 30_000);
    this.reconnectAttempts += 1;
    this.logger.warn({ statusCode, delayMs, error: formatError(lastDisconnect?.error) }, "WhatsApp closed, reconnecting");
    this._scheduleReconnect(delayMs);
  }

  _scheduleReconnect(delayMs) {
    if (this.stopped) return;
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this._connect().catch((err) => this.logger.error({ err }, "reconnect failed"));
    }, delayMs);
  }

  async _handleMessages(event) {
    const { type: eventType, messages } = event;
    if (!["notify", "append"].includes(eventType) || !Array.isArray(messages)) return;
    if (eventType === "append" && !this.config.processAppendMessages) {
      this.logger.info({ count: messages.length }, "ignored append batch");
      return;
    }
    for (const message of messages) {
      await this._handleMessage(message, eventType);
    }
  }

  async _handleMessage(message, eventType) {
    const chatJid = normalizeSenderJid(message?.key?.remoteJid ?? "");
    if (!chatJid || isStatusJid(chatJid)) return;

    const isGroup = isGroupJid(chatJid);
    if (!this.config.allowGroups && isGroup) return;

    const text = extractMessageText(message);
    if (!text) return;

    // Startup warmup guard
    if (this.connectedAtMs && Date.now() - this.connectedAtMs < this.config.startupWarmupMs) {
      this.logger.info({ chatJid }, "ignored message during startup warmup");
      return;
    }

    const isFromMe = Boolean(message?.key?.fromMe);
    const senderJid = normalizeSenderJid(message?.key?.participant ?? chatJid);
    const senderPhone = jidToPhone(isGroup ? senderJid : chatJid);

    // Ignore outbound messages (we only process inbound)
    if (isFromMe) return;

    const messageTimestampMs = parseTimestampMs(message?.messageTimestamp);
    if (
      messageTimestampMs &&
      this.connectedAtMs &&
      messageTimestampMs < this.connectedAtMs - this.config.pairingGraceMs
    ) {
      this.logger.info({ chatJid }, "ignored pre-session pending message");
      return;
    }

    // Deduplication
    const handledKey = buildHandledMessageKey(message, chatJid);
    if (handledKey && this.processingMessageKeys.has(handledKey)) return;
    if (handledKey && this.processedMessageStore.has(handledKey)) return;

    // Mark read
    if (this.config.markRead && message?.key && this.sock && !isGroup) {
      this.sock.readMessages([{
        remoteJid: chatJid,
        id: message.key.id,
        participant: message.key.participant,
        fromMe: false,
      }]).catch((err) => this.logger.warn({ err }, "failed to mark read"));
    }

    this.logger.info({ chatJid, senderJid, text, isGroup }, "received inbound WhatsApp message");

    if (handledKey) {
      this.processingMessageKeys.add(handledKey);
      await this.processedMessageStore.mark(handledKey).catch(() => {});
    }

    try {
      if (!this.config.autoReply || !this.sock) return;

      // Detect if quoted message is from bot (for group reply-based activation)
      const quotedParticipant = message?.message?.extendedTextMessage?.contextInfo?.participant ?? "";
      const selfJid = this.sock.user?.id ?? "";
      const quotedFromMe = Boolean(quotedParticipant && normalizeSenderJid(quotedParticipant) === normalizeSenderJid(selfJid));

      // Dispatch to control plane — it will check dmPolicy/mention and route to agent
      const replyText = await this.controlPlane.sendInbound({
        channel: "whatsapp",
        chat_jid: chatJid,
        sender_jid: senderJid,
        sender_phone: senderPhone,
        text,
        message_id: message?.key?.id ?? "",
        push_name: message?.pushName ?? "",
        is_group: isGroup,
        quoted_from_me: quotedFromMe,
      });

      if (!replyText?.trim()) {
        this.logger.warn({ chatJid }, "control plane returned empty reply");
        return;
      }

      await this.sock.sendPresenceUpdate("composing", chatJid);
      const result = await this.sock.sendMessage(chatJid, { text: replyText });
      this.logger.info({ chatJid, messageId: result?.key?.id }, "sent WhatsApp reply");
    } catch (error) {
      this.logger.error({ error, chatJid }, "failed to handle inbound message");
    } finally {
      if (handledKey) this.processingMessageKeys.delete(handledKey);
    }
  }
}
