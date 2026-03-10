import path from "node:path";
import { fileURLToPath } from "node:url";

import dotenv from "dotenv";

function parseBoolean(value, fallback) {
  if (value == null || value === "") {
    return fallback;
  }
  const normalized = String(value).trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }
  return fallback;
}

function parseList(value) {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeJid(value) {
  if (!value) {
    return "";
  }
  const trimmed = String(value).trim();
  if (trimmed.includes("@")) {
    return trimmed;
  }
  const digits = trimmed.replace(/\D+/g, "");
  return digits ? `${digits}@s.whatsapp.net` : "";
}

function normalizePhone(value) {
  if (!value) {
    return "";
  }
  return String(value).replace(/\D+/g, "");
}

export function loadConfig() {
  const rootDir = path.resolve(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".."));
  dotenv.config({ path: path.join(rootDir, ".env") });
  const soulHome = path.join(rootDir, ".soul");
  const gatewayHome = path.join(soulHome, "gateway");

  return {
    rootDir,
    soulHome,
    gatewayHome,
    authDir: path.join(gatewayHome, "auth"),
    outboxDir: path.join(gatewayHome, "outbox"),
    sentDir: path.join(gatewayHome, "sent"),
    failedDir: path.join(gatewayHome, "failed"),
    logsDir: path.join(gatewayHome, "logs"),
    logFile: path.join(gatewayHome, "logs", "gateway.log"),
    lockFile: path.join(gatewayHome, "gateway.lock"),
    pythonBin: process.env.SOUL_GATEWAY_PYTHON || path.join(rootDir, ".venv", "bin", "python3"),
    soulBridgeScript:
      process.env.SOUL_GATEWAY_BRIDGE_SCRIPT || path.join(rootDir, "scripts", "run_gateway_request.py"),
    allowGroups: parseBoolean(process.env.SOUL_GATEWAY_ALLOW_GROUPS, false),
    allowFromMe: parseBoolean(process.env.SOUL_GATEWAY_ALLOW_FROM_ME, false),
    autoReply: parseBoolean(process.env.SOUL_GATEWAY_AUTO_REPLY, true),
    outboxPollMs: Number.parseInt(process.env.SOUL_GATEWAY_OUTBOX_POLL_MS || "5000", 10),
    markRead: parseBoolean(process.env.SOUL_GATEWAY_MARK_READ, true),
    pairingPhone: normalizePhone(process.env.SOUL_GATEWAY_PAIRING_PHONE || ""),
    allowedFrom: parseList(process.env.SOUL_GATEWAY_ALLOWED_FROM).map(normalizeJid).filter(Boolean),
    defaultTo: normalizeJid(process.env.SOUL_WHATSAPP_DEFAULT_TO || ""),
  };
}
