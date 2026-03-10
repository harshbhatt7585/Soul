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
  const allowedFrom = parseList(process.env.SOUL_GATEWAY_ALLOWED_FROM).map(normalizeJid).filter(Boolean);
  const dmPolicy = String(
    process.env.SOUL_GATEWAY_DM_POLICY
      || process.env.DM_POLICY
      || (allowedFrom.length > 0 ? "allowlist" : "open"),
  ).trim().toLowerCase();
  const wsPort = Number.parseInt(process.env.SOUL_GATEWAY_WS_PORT || process.env.WS_PORT || "9090", 10);
  const wsSecret = process.env.SOUL_GATEWAY_WS_SECRET || process.env.WS_SECRET || "";

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
    bridgeTimeoutMs: Number.parseInt(process.env.SOUL_GATEWAY_BRIDGE_TIMEOUT_MS || "120000", 10),
    allowGroups: parseBoolean(process.env.SOUL_GATEWAY_ALLOW_GROUPS, false),
    allowFromMe: parseBoolean(process.env.SOUL_GATEWAY_ALLOW_FROM_ME, false),
    autoReply: parseBoolean(process.env.SOUL_GATEWAY_AUTO_REPLY, true),
    processAppendMessages: parseBoolean(process.env.SOUL_GATEWAY_PROCESS_APPEND_MESSAGES, false),
    freshStartOnBoot: parseBoolean(process.env.SOUL_GATEWAY_FRESH_START_ON_BOOT, true),
    outboxPollMs: Number.parseInt(process.env.SOUL_GATEWAY_OUTBOX_POLL_MS || "5000", 10),
    pairingGraceMs: Number.parseInt(process.env.SOUL_GATEWAY_PAIRING_GRACE_MS || "30000", 10),
    startupWarmupMs: Number.parseInt(
      process.env.SOUL_GATEWAY_STARTUP_IGNORE_ALL_MESSAGES_MS
        || process.env.SOUL_GATEWAY_STARTUP_IGNORE_FROM_ME_MS
        || "30000",
      10,
    ),
    markRead: parseBoolean(process.env.SOUL_GATEWAY_MARK_READ, true),
    dmPolicy,
    mentionPatterns: parseList(
      process.env.SOUL_GATEWAY_MENTION_PATTERNS || process.env.MENTION_PATTERNS || "",
    ),
    botName: process.env.SOUL_GATEWAY_BOT_NAME || process.env.BOT_NAME || "Soul",
    sessionTtlMs: Number.parseInt(process.env.SOUL_GATEWAY_SESSION_TTL_MS || "1800000", 10),
    wsPort,
    wsSecret,
    controlPlaneUrl: process.env.SOUL_GATEWAY_CONTROL_PLANE_URL || `ws://127.0.0.1:${wsPort}`,
    controlPlaneSecret: process.env.SOUL_GATEWAY_CONTROL_PLANE_SECRET || wsSecret,
    processedMessagesFile: path.join(gatewayHome, "processed-messages.json"),
    processedMessagesTtlMs: Number.parseInt(
      process.env.SOUL_GATEWAY_PROCESSED_MESSAGE_TTL_MS || String(14 * 24 * 60 * 60 * 1000),
      10,
    ),
    processedMessagesMaxEntries: Number.parseInt(
      process.env.SOUL_GATEWAY_PROCESSED_MESSAGE_MAX_ENTRIES || "5000",
      10,
    ),
    pairingPhone: normalizePhone(process.env.SOUL_GATEWAY_PAIRING_PHONE || ""),
    allowedFrom,
    defaultTo: normalizeJid(process.env.SOUL_WHATSAPP_DEFAULT_TO || ""),
  };
}
