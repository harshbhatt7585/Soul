import fs from "node:fs/promises";

import { DisconnectReason } from "@whiskeysockets/baileys";
import P from "pino";

import { extractMessageText, isGroupJid, isStatusJid, normalizeSenderJid } from "./message.js";
import { OutboxProcessor } from "./outbox.js";
import { createWaSocket, formatError, getStatusCode } from "./session.js";
import { SoulBridge } from "./soul-bridge.js";

function extractTriggerPrompt(text) {
  const trimmed = typeof text === "string" ? text.trim() : "";
  if (!trimmed) {
    return "";
  }
  const match = /^SOUL(?:\b|:)\s*([\s\S]*)$/i.exec(trimmed);
  if (!match) {
    return "";
  }
  return (match[1] || "").trim();
}

function parseTimestampMs(value) {
  if (value == null) {
    return 0;
  }
  if (typeof value === "number") {
    return value > 1_000_000_000_000 ? value : value * 1000;
  }
  if (typeof value === "bigint") {
    return Number(value > 1_000_000_000_000n ? value : value * 1000n);
  }
  if (typeof value === "string") {
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parseTimestampMs(parsed) : 0;
  }
  if (typeof value === "object" && value !== null) {
    if (typeof value.low === "number") {
      return parseTimestampMs(value.low);
    }
    if (typeof value.toNumber === "function") {
      return parseTimestampMs(value.toNumber());
    }
  }
  return 0;
}

function jidToPhone(jid) {
  if (!jid) {
    return "";
  }
  const user = String(jid).trim().split("@")[0] || "";
  const bare = user.split(":")[0] || user;
  return bare.replace(/\D+/g, "");
}

function isSelfChatMode(selfPhone, allowedFrom, allowFromMe) {
  if (!selfPhone) {
    return Boolean(allowFromMe);
  }
  const normalized = (allowedFrom ?? []).map(jidToPhone).filter(Boolean);
  return normalized.includes(selfPhone) || Boolean(allowFromMe);
}

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
    this.connectedAtMs = 0;
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
        this.sock.ws?.close();
      } catch {
        // best-effort shutdown
      }
      this.sock = null;
    }
    this.connectedAtMs = 0;
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
    const { sock } = await createWaSocket({
      authDir: this.config.authDir,
      logger: this.logger,
      printQr: false,
    });

    sock.ev.on("connection.update", (update) => this._handleConnectionUpdate(update));
    sock.ev.on("messages.upsert", (event) => this._handleMessages(event));
    this.sock = sock;
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
    const { connection, lastDisconnect } = update;

    if (connection === "open") {
      this.reconnectAttempts = 0;
      this.connectedAtMs = Date.now();
      this.logger.info("WhatsApp gateway connected");
      return;
    }

    if (connection !== "close") {
      return;
    }

    const statusCode = getStatusCode(lastDisconnect?.error);
    if (statusCode === DisconnectReason.loggedOut) {
      this.logger.error("WhatsApp session logged out; run the login flow again");
      return;
    }
    if (statusCode === DisconnectReason.connectionReplaced) {
      this.logger.error("WhatsApp connection was replaced by another active session; stopping gateway");
      await this.stop();
      return;
    }

    const delayMs = Math.min(1000 * (2 ** this.reconnectAttempts), 30000);
    this.reconnectAttempts += 1;
    this.logger.warn({ statusCode, delayMs, error: formatError(lastDisconnect?.error) }, "WhatsApp connection closed, reconnecting");
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

  async _handleMessages(event) {
    const eventType = event?.type;
    if ((eventType !== "notify" && eventType !== "append") || !Array.isArray(event.messages)) {
      return;
    }

    for (const message of event.messages) {
      await this._handleMessage(message);
    }
  }

  async _handleMessage(message) {
    const chatJid = normalizeSenderJid(message?.key?.remoteJid || "");
    if (!chatJid || isStatusJid(chatJid)) {
      return;
    }

    const isGroup = isGroupJid(chatJid);
    if (!this.config.allowGroups && isGroup) {
      return;
    }

    const text = extractMessageText(message);
    if (!text) {
      return;
    }

    if (
      this.connectedAtMs
      && Date.now() - this.connectedAtMs < this.config.startupWarmupMs
    ) {
      this.logger.info(
        {
          chatJid,
          startupWarmupMs: this.config.startupWarmupMs,
          connectedAtMs: this.connectedAtMs,
        },
        "ignored message during startup warmup",
      );
      return;
    }

    const isFromMe = Boolean(message?.key?.fromMe);
    const senderJid = normalizeSenderJid(message?.key?.participant || chatJid);
    const senderPhone = jidToPhone(isGroup ? senderJid : chatJid);
    const selfPhone = jidToPhone(this.sock?.user?.id || "");
    const selfChatEnabled = isSelfChatMode(selfPhone, this.config.allowedFrom, this.config.allowFromMe);
    const isSelfChat = Boolean(
      (selfChatEnabled && senderPhone && selfPhone && senderPhone === selfPhone)
      || (this.config.allowFromMe && isFromMe),
    );

    if (isFromMe && !isSelfChat) {
      this.logger.info({ chatJid, senderJid }, "ignored outbound message outside self-chat mode");
      return;
    }

    const allowlistedPhones = this.config.allowedFrom.map(jidToPhone).filter(Boolean);
    if (allowlistedPhones.length > 0 && !allowlistedPhones.includes(senderPhone) && !isSelfChat) {
      this.logger.info({ chatJid, senderJid }, "ignored message from non-allowlisted sender");
      return;
    }

    const messageTimestampMs = parseTimestampMs(message?.messageTimestamp);
    if (
      messageTimestampMs
      && this.connectedAtMs
      && messageTimestampMs < this.connectedAtMs - this.config.pairingGraceMs
    ) {
      this.logger.info(
        { chatJid, text, fromMe: isFromMe, messageTimestampMs, connectedAtMs: this.connectedAtMs },
        "ignored pending message from before current gateway session",
      );
      return;
    }

    const agentText = extractTriggerPrompt(text);
    if (!agentText) {
      this.logger.info({ chatJid, text, fromMe: isFromMe }, "ignored message without SOUL prefix");
      return;
    }

    if (this.config.markRead && message?.key && this.sock && !isSelfChat && !isFromMe) {
      try {
        await this.sock.readMessages([{
          remoteJid: chatJid,
          id: message.key.id,
          participant: message.key.participant,
          fromMe: false,
        }]);
      } catch (error) {
        this.logger.warn({ error: String(error), chatJid }, "failed to mark WhatsApp message as read");
      }
    }

    this.logger.info(
      { chatJid, senderJid, text, agentText, fromMe: isFromMe, isSelfChat },
      "received inbound WhatsApp message",
    );

    if (!this.config.autoReply || !this.sock) {
      return;
    }

    const targetJid = chatJid;
    try {
      const reply = await this.soulBridge.handleInbound({
        channel: "whatsapp",
        sender_jid: senderJid || chatJid,
        text: agentText,
        message_id: message?.key?.id || "",
        push_name: message?.pushName || "",
      });

      const replyText = typeof reply?.reply === "string" ? reply.reply.trim() : "";
      if (!replyText) {
        this.logger.warn({ chatJid }, "Soul bridge returned no reply text");
        return;
      }

      await this.sock.sendPresenceUpdate("composing", targetJid);
      const result = await this.sock.sendMessage(targetJid, { text: replyText });
      this.logger.info(
        { chatJid, targetJid, replyText, messageId: result?.key?.id || "" },
        "sent WhatsApp reply",
      );
    } catch (error) {
      this.logger.error({ error, chatJid }, "failed to handle inbound WhatsApp message");
    }
  }
}
