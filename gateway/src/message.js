export function extractMessageText(message) {
  const content = message?.message;
  if (!content) {
    return "";
  }

  if (typeof content.conversation === "string") {
    return content.conversation.trim();
  }

  if (typeof content.extendedTextMessage?.text === "string") {
    return content.extendedTextMessage.text.trim();
  }

  if (typeof content.imageMessage?.caption === "string") {
    return content.imageMessage.caption.trim();
  }

  if (typeof content.videoMessage?.caption === "string") {
    return content.videoMessage.caption.trim();
  }

  return "";
}

export function isStatusJid(jid) {
  return jid === "status@broadcast";
}

export function isGroupJid(jid) {
  return typeof jid === "string" && jid.endsWith("@g.us");
}

export function normalizeSenderJid(jid) {
  return typeof jid === "string" ? jid.trim() : "";
}
