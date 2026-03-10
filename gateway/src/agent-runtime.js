import { SoulBridge } from "./soul-bridge.js";

const DEFAULT_EMPTY_REPLY = "(I was unable to produce a response — please try again.)";
const HISTORY_LIMIT = 12;

function formatHistory(session, senderLabel) {
  return session.toLLMHistory().slice(-HISTORY_LIMIT).map((turn) => {
    const label = turn.role === "assistant" ? "Assistant" : senderLabel;
    return `${label}: ${turn.content}`;
  }).join("\n");
}

export class AgentRuntime {
  constructor(config, logger) {
    this.config = config;
    this.logger = logger;
    this.bridge = new SoulBridge(config, logger);
  }

  async run({ session, userText, senderJid, pushName, messageId }) {
    session.addTurn("user", userText);
    const senderLabel = pushName || senderJid || "User";
    const prompt = this._buildPrompt({ session, senderLabel, latestUserText: userText });
    const result = await this.bridge.handleInbound({
      channel: "whatsapp",
      sender_jid: senderJid,
      text: prompt,
      message_id: messageId || "",
      push_name: pushName || "",
    });

    const reply = typeof result?.reply === "string" ? result.reply.trim() : "";
    const replyText = reply || DEFAULT_EMPTY_REPLY;
    session.addTurn("assistant", replyText);
    return replyText;
  }

  _buildPrompt({ session, senderLabel, latestUserText }) {
    const history = formatHistory(session, senderLabel);
    if (!history) {
      return latestUserText;
    }
    return [
      "You are replying inside an ongoing WhatsApp conversation.",
      "Use the recent conversation history below to answer the latest user message naturally.",
      "",
      history,
      "",
      "Reply as the assistant to the latest user message only.",
    ].join("\n");
  }
}
