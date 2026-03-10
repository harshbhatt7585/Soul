/**
 * GatewayControlPlane
 *
 * A WebSocket server that acts as the control plane between the WhatsApp
 * gateway process and the Agent Runtime.
 *
 * Protocol (JSON frames):
 *
 *   CLIENT → SERVER  (inbound message from WhatsApp)
 *   {
 *     type: "inbound",
 *     channel: "whatsapp",
 *     chat_jid: string,
 *     sender_jid: string,
 *     sender_phone: string,
 *     text: string,
 *     message_id: string,
 *     push_name: string,
 *     is_group: boolean,
 *     quoted_from_me: boolean,
 *   }
 *
 *   SERVER → CLIENT  (reply to send back on WhatsApp)
 *   {
 *     type: "reply",
 *     chat_jid: string,
 *     text: string,
 *     message_id: string,   // echo of inbound message_id
 *   }
 *
 *   SERVER → CLIENT  (error frame)
 *   {
 *     type: "error",
 *     message_id: string,
 *     error: string,
 *   }
 *
 *   CLIENT → SERVER  (heartbeat ping, optional)
 *   { type: "ping" }
 *
 *   SERVER → CLIENT
 *   { type: "pong" }
 */

import { WebSocketServer, WebSocket } from "ws";

export class GatewayControlPlane {
  /**
   * @param {object} config
   * @param {number} config.wsPort           – port for the WS server (default 9090)
   * @param {string} config.wsSecret         – shared secret for auth (sent as first frame)
   * @param {object} sessionManager          – SessionManager instance
   * @param {object} agentRuntime            – AgentRuntime instance
   * @param {object} logger
   */
  constructor(config, sessionManager, agentRuntime, logger) {
    this.config = config;
    this.sessionManager = sessionManager;
    this.agentRuntime = agentRuntime;
    this.logger = logger;
    this.wss = null;
    this.clients = new Set();
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  start() {
    const port = this.config.wsPort ?? 9090;
    this.wss = new WebSocketServer({ port });

    this.wss.on("connection", (ws, req) => this._onConnection(ws, req));
    this.wss.on("error", (err) => this.logger.error({ err }, "WebSocket server error"));

    this.logger.info({ port }, "Gateway control plane listening");
  }

  stop() {
    for (const ws of this.clients) {
      try { ws.close(); } catch { /* ignore */ }
    }
    this.clients.clear();
    this.wss?.close();
  }

  // ── Connection handling ───────────────────────────────────────────────────

  _onConnection(ws, req) {
    const ip = req.socket.remoteAddress;
    this.logger.info({ ip }, "new gateway client connected");

    let authenticated = false;

    ws.on("message", async (raw) => {
      let frame;
      try {
        frame = JSON.parse(raw.toString());
      } catch {
        this._send(ws, { type: "error", error: "invalid JSON" });
        return;
      }

      // ── Auth handshake ─────────────────────────────────────────────────
      if (!authenticated) {
        if (
          frame.type === "auth" &&
          this.config.wsSecret &&
          frame.secret === this.config.wsSecret
        ) {
          authenticated = true;
          this.clients.add(ws);
          this._send(ws, { type: "auth_ok" });
          this.logger.info({ ip }, "gateway client authenticated");
        } else if (!this.config.wsSecret) {
          // No secret configured — allow all local connections
          authenticated = true;
          this.clients.add(ws);
          this._send(ws, { type: "auth_ok" });
        } else {
          this._send(ws, { type: "error", error: "unauthorized" });
          ws.close();
        }
        return;
      }

      // ── Dispatch by frame type ─────────────────────────────────────────
      switch (frame.type) {
        case "ping":
          this._send(ws, { type: "pong" });
          break;

        case "inbound":
          await this._handleInbound(ws, frame);
          break;

        default:
          this._send(ws, { type: "error", error: `unknown frame type: ${frame.type}` });
      }
    });

    ws.on("close", () => {
      this.clients.delete(ws);
      this.logger.info({ ip }, "gateway client disconnected");
    });

    ws.on("error", (err) => {
      this.logger.warn({ ip, err }, "gateway client WebSocket error");
    });
  }

  // ── Inbound message dispatch ──────────────────────────────────────────────

  async _handleInbound(ws, frame) {
    const {
      chat_jid,
      sender_jid,
      sender_phone,
      text,
      message_id,
      push_name,
      is_group,
      quoted_from_me,
    } = frame;

    if (!chat_jid || !text) {
      this._send(ws, { type: "error", message_id, error: "missing chat_jid or text" });
      return;
    }

    // ── Session activation check ─────────────────────────────────────────
    const shouldRespond = this.sessionManager.shouldRespond({
      chatJid: chat_jid,
      senderPhone: sender_phone,
      senderJid: sender_jid,
      text,
      isGroup: Boolean(is_group),
      quotedMessageFromMe: Boolean(quoted_from_me),
    });

    if (!shouldRespond) {
      this.logger.info({ chat_jid, message_id }, "control plane: skipping message (policy)");
      return;
    }

    // Strip mention tokens so the LLM gets a clean prompt
    const cleanText = Boolean(is_group)
      ? this.sessionManager.stripMention(text)
      : text;

    // Get or create session
    const session = this.sessionManager.getOrCreate(chat_jid, { isGroup: Boolean(is_group) });

    try {
      const reply = await this.agentRuntime.run({
        session,
        userText: cleanText,
        senderJid: sender_jid,
        pushName: push_name,
      });

      this._send(ws, {
        type: "reply",
        chat_jid,
        text: reply,
        message_id,
      });

      this.logger.info({ chat_jid, message_id, replyLength: reply.length }, "control plane: reply dispatched");
    } catch (error) {
      this.logger.error({ error, chat_jid, message_id }, "control plane: agent runtime error");
      this._send(ws, {
        type: "error",
        message_id,
        error: String(error?.message ?? error),
      });
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  _send(ws, obj) {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }

  /**
   * Broadcast a proactive message to all connected gateway clients.
   * Used by the heartbeat to push unsolicited messages.
   */
  broadcast(frame) {
    for (const ws of this.clients) {
      this._send(ws, frame);
    }
  }
}
