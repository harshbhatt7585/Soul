import { WebSocket, WebSocketServer } from "ws";

export class GatewayControlPlane {
  constructor(config, sessionManager, agentRuntime, logger) {
    this.config = config;
    this.sessionManager = sessionManager;
    this.agentRuntime = agentRuntime;
    this.logger = logger;
    this.wss = null;
    this.clients = new Set();
  }

  start() {
    const port = this.config.wsPort ?? 9090;
    this.wss = new WebSocketServer({ port });
    this.wss.on("connection", (ws, req) => this._onConnection(ws, req));
    this.wss.on("error", (error) => this.logger.error({ error }, "WebSocket server error"));
    this.logger.info({ port }, "Gateway control plane listening");
  }

  stop() {
    for (const ws of this.clients) {
      try {
        ws.close();
      } catch {
        // ignore
      }
    }
    this.clients.clear();
    this.wss?.close();
  }

  _onConnection(ws, req) {
    const ip = req.socket.remoteAddress;
    this.logger.info({ ip }, "new gateway client connected");
    let authenticated = false;

    if (!this.config.wsSecret) {
      authenticated = true;
      this.clients.add(ws);
      this._send(ws, { type: "auth_ok" });
      this.logger.info({ ip }, "gateway client authenticated (no secret configured)");
    }

    ws.on("message", async (raw) => {
      let frame;
      try {
        frame = JSON.parse(raw.toString());
      } catch {
        this._send(ws, { type: "error", error: "invalid JSON" });
        return;
      }

      if (!authenticated) {
        if (
          frame.type === "auth"
          && this.config.wsSecret
          && frame.secret === this.config.wsSecret
        ) {
          authenticated = true;
          this.clients.add(ws);
          this._send(ws, { type: "auth_ok" });
          this.logger.info({ ip }, "gateway client authenticated");
        } else {
          this._send(ws, { type: "error", error: "unauthorized" });
          ws.close();
        }
        return;
      }

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

    ws.on("error", (error) => {
      this.logger.warn({ ip, error }, "gateway client WebSocket error");
    });
  }

  async _handleInbound(ws, frame) {
    const {
      chat_jid: chatJid,
      sender_jid: senderJid,
      sender_phone: senderPhone,
      text,
      message_id: messageId,
      push_name: pushName,
      is_group: isGroup,
      quoted_from_me: quotedFromMe,
      force_respond: forceRespond,
    } = frame;

    if (!chatJid || !text) {
      this._send(ws, { type: "error", message_id: messageId, error: "missing chat_jid or text" });
      return;
    }

    const shouldRespond = forceRespond || this.sessionManager.shouldRespond({
      senderPhone,
      senderJid,
      text,
      isGroup: Boolean(isGroup),
      quotedMessageFromMe: Boolean(quotedFromMe),
    });

    if (!shouldRespond) {
      this.logger.info({ chatJid, messageId }, "control plane: skipping message (policy)");
      this._send(ws, { type: "reply", chat_jid: chatJid, text: "", message_id: messageId });
      return;
    }

    const cleanText = Boolean(isGroup) && !forceRespond
      ? this.sessionManager.stripMention(text)
      : text;
    const session = this.sessionManager.getOrCreate(chatJid, { isGroup: Boolean(isGroup) });

    try {
      const reply = await this.agentRuntime.run({
        session,
        userText: cleanText,
        senderJid,
        pushName,
        messageId,
      });

      this._send(ws, {
        type: "reply",
        chat_jid: chatJid,
        text: reply,
        message_id: messageId,
      });
      this.logger.info({ chatJid, messageId, replyLength: reply.length }, "control plane: reply dispatched");
    } catch (error) {
      this.logger.error({ error, chatJid, messageId }, "control plane: agent runtime error");
      this._send(ws, {
        type: "error",
        message_id: messageId,
        error: String(error?.message ?? error),
      });
    }
  }

  _send(ws, obj) {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }
}
