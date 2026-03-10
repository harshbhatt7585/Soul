import fs from "node:fs";
import fsPromises from "node:fs/promises";
import path from "node:path";

import {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  makeWASocket,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";

let credsSaveQueue = Promise.resolve();
const CREDS_FILE = "creds.json";
const CREDS_BACKUP_FILE = "creds.backup.json";

function resolveCredsPath(authDir) {
  return path.join(authDir, CREDS_FILE);
}

function resolveCredsBackupPath(authDir) {
  return path.join(authDir, CREDS_BACKUP_FILE);
}

function readCredsJsonRaw(filePath) {
  try {
    if (!fs.existsSync(filePath)) {
      return null;
    }
    const stats = fs.statSync(filePath);
    if (!stats.isFile() || stats.size <= 1) {
      return null;
    }
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

function maybeRestoreCredsFromBackup(authDir, logger) {
  const credsPath = resolveCredsPath(authDir);
  const backupPath = resolveCredsBackupPath(authDir);
  try {
    const raw = readCredsJsonRaw(credsPath);
    if (raw) {
      JSON.parse(raw);
      return;
    }
  } catch {
    // fall through to backup restore
  }

  try {
    const backupRaw = readCredsJsonRaw(backupPath);
    if (!backupRaw) {
      return;
    }
    JSON.parse(backupRaw);
    fs.copyFileSync(backupPath, credsPath);
    try {
      fs.chmodSync(credsPath, 0o600);
    } catch {
      // best-effort permission hardening
    }
    logger.warn({ credsPath, backupPath }, "restored WhatsApp creds from backup");
  } catch (error) {
    logger.warn({ error: String(error), backupPath }, "failed restoring WhatsApp creds backup");
  }
}

async function safeSaveCreds(authDir, saveCreds, logger) {
  try {
    const credsPath = resolveCredsPath(authDir);
    const backupPath = resolveCredsBackupPath(authDir);
    const raw = readCredsJsonRaw(credsPath);
    if (raw) {
      JSON.parse(raw);
      fs.copyFileSync(credsPath, backupPath);
      try {
        fs.chmodSync(backupPath, 0o600);
      } catch {
        // best-effort permission hardening
      }
    }
  } catch {
    // best-effort preflight validation only
  }

  try {
    await Promise.resolve(saveCreds());
    try {
      fs.chmodSync(resolveCredsPath(authDir), 0o600);
    } catch {
      // best-effort permission hardening
    }
  } catch (error) {
    logger.warn({ error: String(error) }, "failed saving WhatsApp creds");
  }
}

function enqueueSaveCreds(authDir, saveCreds, logger) {
  credsSaveQueue = credsSaveQueue
    .then(() => safeSaveCreds(authDir, saveCreds, logger))
    .catch((error) => {
      logger.warn({ error: String(error) }, "WhatsApp creds save queue error");
    });
}

export async function createWaSocket({ authDir, logger, printQr = false, onQr, browser } = {}) {
  await fsPromises.mkdir(authDir, { recursive: true });
  maybeRestoreCredsFromBackup(authDir, logger);

  const { state, saveCreds } = await useMultiFileAuthState(authDir);
  const { version, isLatest } = await fetchLatestBaileysVersion().catch((error) => {
    logger.warn({ error: String(error) }, "failed to fetch latest Baileys version, using bundled default");
    return { version: undefined, isLatest: false };
  });

  const sock = makeWASocket({
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    printQRInTerminal: false,
    browser: browser ?? ["openclaw", "cli", "soul"],
    syncFullHistory: false,
    markOnlineOnConnect: false,
    shouldSyncHistoryMessage: () => false,
    ...(version ? { version } : {}),
  });

  if (version) {
    logger.info({ version, isLatest }, "using WhatsApp Web version");
  }

  sock.ev.on("creds.update", () => enqueueSaveCreds(authDir, saveCreds, logger));
  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      onQr?.(qr);
      if (printQr) {
        console.log("Scan this QR in WhatsApp (Linked Devices):");
        qrcode.generate(qr, { small: true });
      }
    }
    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      if (statusCode === DisconnectReason.loggedOut) {
        logger.error("WhatsApp session logged out");
      }
    }
  });
  if (sock.ws && typeof sock.ws.on === "function") {
    sock.ws.on("error", (error) => {
      logger.error({ error: String(error) }, "WebSocket error");
    });
  }

  return {
    sock,
    registered: Boolean(state.creds.registered),
  };
}

export async function waitForWaConnection(sock) {
  return new Promise((resolve, reject) => {
    const handler = (update) => {
      if (update?.connection === "open") {
        sock.ev.off?.("connection.update", handler);
        resolve();
        return;
      }
      if (update?.connection === "close") {
        sock.ev.off?.("connection.update", handler);
        reject(update?.lastDisconnect ?? new Error("Connection closed"));
      }
    };
    sock.ev.on("connection.update", handler);
  });
}

export function getStatusCode(error) {
  return error?.output?.statusCode ?? error?.status;
}

function safeStringify(value, limit = 800) {
  try {
    const seen = new WeakSet();
    const raw = JSON.stringify(
      value,
      (_key, current) => {
        if (typeof current === "bigint") {
          return current.toString();
        }
        if (typeof current === "function") {
          return `[Function ${current.name || "anonymous"}]`;
        }
        if (typeof current === "object" && current) {
          if (seen.has(current)) {
            return "[Circular]";
          }
          seen.add(current);
        }
        return current;
      },
      2,
    );
    if (!raw) {
      return String(value);
    }
    return raw.length > limit ? `${raw.slice(0, limit)}...` : raw;
  } catch {
    return String(value);
  }
}

function extractBoomDetails(error) {
  if (!error || typeof error !== "object") {
    return null;
  }
  const output = error.output;
  if (!output || typeof output !== "object") {
    return null;
  }
  const payload = output.payload;
  const statusCode = typeof output.statusCode === "number"
    ? output.statusCode
    : typeof payload?.statusCode === "number"
      ? payload.statusCode
      : undefined;
  const code = typeof payload?.error === "string" ? payload.error : undefined;
  const message = typeof payload?.message === "string" ? payload.message : undefined;
  if (!statusCode && !code && !message) {
    return null;
  }
  return { statusCode, code, message };
}

export function formatError(error) {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  if (!error || typeof error !== "object") {
    return String(error);
  }

  const boom = extractBoomDetails(error) ?? extractBoomDetails(error.error) ?? extractBoomDetails(error.lastDisconnect?.error);
  const status = boom?.statusCode ?? getStatusCode(error);
  const code = error.code;
  const codeText = typeof code === "string" || typeof code === "number" ? String(code) : undefined;
  const message = [
    boom?.message,
    typeof error.message === "string" ? error.message : undefined,
    typeof error.error?.message === "string" ? error.error.message : undefined,
  ].filter((value) => Boolean(value && value.trim().length > 0))[0];

  const parts = [];
  if (typeof status === "number") {
    parts.push(`status=${status}`);
  }
  if (boom?.code) {
    parts.push(boom.code);
  }
  if (message) {
    parts.push(message);
  }
  if (codeText) {
    parts.push(`code=${codeText}`);
  }
  if (parts.length > 0) {
    return parts.join(" ");
  }
  return safeStringify(error);
}
