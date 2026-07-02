import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import makeWASocket, {
  Browsers,
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys";
import QRCode from "qrcode";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  const key = process.argv[index];
  const value = process.argv[index + 1];
  if (key?.startsWith("--")) args.set(key.slice(2), value);
}

const host = args.get("host") || process.env.WHATSAPP_GATEWAY_RUNTIME_HOST || "127.0.0.1";
const port = Number(args.get("port") || process.env.WHATSAPP_GATEWAY_RUNTIME_PORT || 3020);
const token = args.get("token") || process.env.WHATSAPP_GATEWAY_RUNTIME_TOKEN || "";
const backendEventUrl =
  args.get("backend-event-url") ||
  process.env.WHATSAPP_GATEWAY_BACKEND_EVENT_URL ||
  "http://127.0.0.1:8000/api/whatsapp-gateway/runtime/events";
const eventToken = args.get("event-token") || process.env.WHATSAPP_GATEWAY_EVENT_TOKEN || "";
const dataDir = path.resolve(
  args.get("data-dir") || process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR || path.join(projectRoot, ".runtime", "baileys"),
);

const instances = new Map();

const logger = {
  level: "silent",
  trace() {},
  debug() {},
  info() {},
  warn() {},
  error() {},
  child() {
    return logger;
  },
};

function nowIso() {
  return new Date().toISOString();
}

function logRuntime(event, payload = {}) {
  console.log(JSON.stringify({ ts: nowIso(), event, ...payload }));
}

function baseState(instanceId) {
  return {
    instanceId,
    status: "disconnected",
    qrCode: null,
    qrCodeDataUrl: null,
    phoneNumber: null,
    lastError: null,
    connectedAt: null,
    disconnectedAt: null,
    lastSeenAt: null,
    startedAt: null,
    socket: null,
    reconnectAttempts: 0,
    pairingCode: null,
  };
}

function getState(instanceId) {
  if (!instances.has(instanceId)) {
    instances.set(instanceId, baseState(instanceId));
  }
  return instances.get(instanceId);
}

function publicState(state) {
  return {
    instance_id: state.instanceId,
    status: state.status,
    qr_code: state.qrCode,
    qr_code_data_url: state.qrCodeDataUrl,
    phone_number: state.phoneNumber,
    last_error: state.lastError,
    connected_at: state.connectedAt,
    disconnected_at: state.disconnectedAt,
    last_seen_at: state.lastSeenAt,
    started_at: state.startedAt,
    reconnect_attempts: state.reconnectAttempts,
    pairing_code: state.pairingCode,
  };
}

function normalizePhoneJid(phone) {
  const value = String(phone || "").trim();
  if (!value) return null;
  if (value.endsWith("@s.whatsapp.net") || value.endsWith("@g.us")) return value;
  let digits = value.replace(/\D/g, "");
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (!digits.startsWith("55") && [10, 11].includes(digits.length)) {
    digits = `55${digits}`;
  }
  return digits ? `${digits}@s.whatsapp.net` : null;
}

function jidToPhone(jid) {
  return String(jid || "").split("@", 1)[0] || null;
}

function assertConnected(state) {
  if (!state.socket || state.status !== "connected") {
    return fail("not_connected", "Instancia Baileys nao esta conectada.", publicState(state));
  }
  return null;
}

function jsonSafe(value) {
  return JSON.parse(
    JSON.stringify(value, (_key, item) => {
      if (typeof item === "bigint") return item.toString();
      if (Buffer.isBuffer(item)) return item.toString("base64");
      return item;
    }),
  );
}

function messageTimestamp(value) {
  if (!value) return nowIso();
  if (typeof value === "number") return new Date(value * 1000).toISOString();
  if (typeof value === "bigint") return new Date(Number(value) * 1000).toISOString();
  if (typeof value === "object" && typeof value.toNumber === "function") {
    return new Date(value.toNumber() * 1000).toISOString();
  }
  return nowIso();
}

function unwrapMessage(message) {
  let current = message || {};
  for (let index = 0; index < 4; index += 1) {
    if (current.ephemeralMessage?.message) current = current.ephemeralMessage.message;
    else if (current.viewOnceMessage?.message) current = current.viewOnceMessage.message;
    else if (current.viewOnceMessageV2?.message) current = current.viewOnceMessageV2.message;
    else break;
  }
  return current;
}

function quotedProviderMessageId(message) {
  const entries = [
    message?.extendedTextMessage,
    message?.imageMessage,
    message?.videoMessage,
    message?.audioMessage,
    message?.documentMessage,
    message?.stickerMessage,
  ].filter(Boolean);
  for (const entry of entries) {
    const quoted = entry?.contextInfo?.stanzaId || entry?.contextInfo?.quotedMessageId;
    if (quoted) return String(quoted);
  }
  return null;
}

function mediaExtension(mimetype = "") {
  const value = String(mimetype || "").toLowerCase().split(";", 1)[0];
  if (value === "audio/ogg") return "ogg";
  if (value === "audio/opus") return "opus";
  if (value === "audio/mpeg" || value === "audio/mp3") return "mp3";
  if (value === "audio/mp4") return "m4a";
  if (value === "audio/webm") return "webm";
  if (value === "video/mp4") return "mp4";
  return "bin";
}

function mediaReference(mediaUrl = "") {
  const value = String(mediaUrl || "").trim();
  if (value.startsWith("/uploads/") || value.startsWith("uploads/")) {
    return { url: path.join(projectRoot, value.replace(/^\/+/, "")) };
  }
  return { url: value };
}

function numericValue(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (typeof value?.toNumber === "function") {
    const parsed = value.toNumber();
    return Number.isFinite(parsed) ? parsed : null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

async function storeInboundMedia(item, media, messageType, providerMessageId) {
  if (!media || !["audio"].includes(messageType)) {
    return { media_url: media?.url || null, media_storage_key: null, media_size_bytes: numericValue(media?.fileLength) };
  }
  try {
    const buffer = await downloadMediaMessage(item, "buffer", {}, { logger });
    if (!buffer || !buffer.length) {
      return { media_url: media.url || null, media_storage_key: null, media_size_bytes: numericValue(media.fileLength) };
    }
    const mimetype = media.mimetype || (messageType === "audio" ? "audio/ogg" : "application/octet-stream");
    const dir = path.join(projectRoot, "uploads", "agente-whatsapp-audio");
    await fs.mkdir(dir, { recursive: true });
    const filename = `${providerMessageId}-${randomUUID()}.${mediaExtension(mimetype)}`;
    const absolutePath = path.join(dir, filename);
    await fs.writeFile(absolutePath, buffer);
    const storageKey = path.relative(projectRoot, absolutePath).replaceAll("\\", "/");
    return {
      media_url: `/${storageKey}`,
      media_storage_key: storageKey,
      media_mime_type: mimetype,
      media_size_bytes: buffer.length,
      media_duration_ms: numericValue(media.seconds) ? numericValue(media.seconds) * 1000 : null,
    };
  } catch (error) {
    return {
      media_url: media.url || null,
      media_storage_key: null,
      media_download_error: error instanceof Error ? error.message : String(error),
      media_mime_type: media.mimetype || null,
      media_size_bytes: numericValue(media.fileLength),
      media_duration_ms: numericValue(media.seconds) ? numericValue(media.seconds) * 1000 : null,
    };
  }
}

async function extractInboundMessage(item) {
  const key = item?.key || {};
  if (key.fromMe) return null;
  const remoteJid = key.remoteJid || item?.remoteJid || "";
  if (!remoteJid || remoteJid.endsWith("@broadcast")) return null;

  const message = unwrapMessage(item?.message);
  const providerMessageId = key.id || item?.messageID || item?.messageId;
  if (!providerMessageId || !message || Object.keys(message).length === 0) return null;
  const quotedId = quotedProviderMessageId(message);

  if (message.conversation) {
    return {
      id: providerMessageId,
      remote_jid: remoteJid,
      phone: remoteJid.split("@", 1)[0],
      push_name: item?.pushName || null,
      from_me: false,
      message_type: "text",
      body: message.conversation,
      media_url: null,
      quoted_provider_message_id: quotedId,
      timestamp: messageTimestamp(item?.messageTimestamp),
      raw_payload: jsonSafe(item),
    };
  }

  if (message.extendedTextMessage) {
    return {
      id: providerMessageId,
      remote_jid: remoteJid,
      phone: remoteJid.split("@", 1)[0],
      push_name: item?.pushName || null,
      from_me: false,
      message_type: "text",
      body: message.extendedTextMessage.text || "",
      media_url: null,
      quoted_provider_message_id: quotedId,
      timestamp: messageTimestamp(item?.messageTimestamp),
      raw_payload: jsonSafe(item),
    };
  }

  const mediaEntries = [
    ["image", message.imageMessage],
    ["video", message.videoMessage],
    ["audio", message.audioMessage],
    ["document", message.documentMessage],
    ["sticker", message.stickerMessage],
  ].filter(([, value]) => value);
  if (mediaEntries.length) {
    const [messageType, media] = mediaEntries[0];
    const storedMedia = await storeInboundMedia(item, media, messageType, providerMessageId);
    return {
      id: providerMessageId,
      remote_jid: remoteJid,
      phone: remoteJid.split("@", 1)[0],
      push_name: item?.pushName || null,
      from_me: false,
      message_type: messageType,
      body: media.caption || media.fileName || null,
      media_url: storedMedia.media_url || null,
      media_storage_key: storedMedia.media_storage_key || null,
      media_mime_type: storedMedia.media_mime_type || media.mimetype || null,
      media_duration_ms: storedMedia.media_duration_ms || null,
      media_size_bytes: storedMedia.media_size_bytes || numericValue(media.fileLength),
      media_download_error: storedMedia.media_download_error || null,
      quoted_provider_message_id: quotedId,
      timestamp: messageTimestamp(item?.messageTimestamp),
      raw_payload: jsonSafe(item),
    };
  }

  return {
    id: providerMessageId,
    remote_jid: remoteJid,
    phone: remoteJid.split("@", 1)[0],
    push_name: item?.pushName || null,
    from_me: false,
    message_type: "unknown",
    body: JSON.stringify(jsonSafe(message)),
    media_url: null,
    quoted_provider_message_id: quotedId,
    timestamp: messageTimestamp(item?.messageTimestamp),
    raw_payload: jsonSafe(item),
  };
}

async function postBackendEvent(payload) {
  if (!backendEventUrl) return;
  const headers = { "content-type": "application/json" };
  if (eventToken) headers["x-whatsapp-gateway-token"] = eventToken;
  const response = await fetch(backendEventUrl, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Backend event HTTP ${response.status}`);
  }
}

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (!chunks.length) return {};
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw.trim()) return {};
  return JSON.parse(raw);
}

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, { "content-type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(payload));
}

function ok(message, data = {}) {
  return { ok: true, message, data };
}

function fail(status, message, data = {}) {
  return { ok: false, status, message, data };
}

function assertAuthorized(request) {
  if (!token) return true;
  return request.headers.authorization === `Bearer ${token}`;
}

async function makeQrDataUrl(qr) {
  return QRCode.toDataURL(qr, {
    errorCorrectionLevel: "M",
    margin: 1,
    width: 320,
    color: {
      dark: "#111111",
      light: "#ffffff",
    },
  });
}

async function connectInstance(instanceId, body = {}) {
  const state = getState(instanceId);
  if (state.socket && ["connecting", "connected", "qr_required"].includes(state.status)) {
    return ok("Instancia Baileys ja esta em execucao.", publicState(state));
  }

  const sessionDir = path.join(dataDir, "sessions", instanceId);
  await fs.mkdir(sessionDir, { recursive: true });

  state.status = "connecting";
  state.startedAt = nowIso();
  state.lastSeenAt = nowIso();
  state.lastError = null;
  state.qrCode = null;
  state.qrCodeDataUrl = null;
  if (!body.reconnect) state.reconnectAttempts = 0;

  const { state: authState, saveCreds } = await useMultiFileAuthState(sessionDir);
  const versionResult = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));
  logRuntime("instance_connect_start", {
    instance_id: instanceId,
    baileys_version: versionResult.version?.join?.(".") || null,
    reconnect: Boolean(body.reconnect),
    reconnect_attempts: state.reconnectAttempts,
  });
  const socket = makeWASocket({
    auth: authState,
    browser: Browsers.ubuntu("Chrome"),
    printQRInTerminal: false,
    logger,
    ...(versionResult.version ? { version: versionResult.version } : {}),
  });

  state.socket = socket;
  state.displayName = body.name || null;

  socket.ev.on("creds.update", saveCreds);
  socket.ev.on("messages.upsert", async ({ messages }) => {
    for (const item of messages || []) {
      const inbound = await extractInboundMessage(item);
      if (!inbound) continue;
      await postBackendEvent({
        event_type: "message_received",
        provider: "baileys",
        instance_id: instanceId,
        message: inbound,
        payload: {
          received_at: nowIso(),
          instance_name: state.displayName,
        },
      }).catch((error) => {
        state.lastError = error instanceof Error ? error.message : String(error);
      });
    }
  });
  socket.ev.on("connection.update", async (update) => {
    state.lastSeenAt = nowIso();

    if (update.qr) {
      state.status = "qr_required";
      state.qrCode = update.qr;
      state.qrCodeDataUrl = await makeQrDataUrl(update.qr).catch((error) => {
        state.lastError = error instanceof Error ? error.message : String(error);
        logRuntime("instance_qr_error", {
          instance_id: instanceId,
          error: state.lastError,
        });
        return null;
      });
      logRuntime("instance_qr_ready", {
        instance_id: instanceId,
        has_qr_data_url: Boolean(state.qrCodeDataUrl),
      });
    }

    if (update.connection === "open") {
      state.status = "connected";
      state.qrCode = null;
      state.qrCodeDataUrl = null;
      state.connectedAt = nowIso();
      state.disconnectedAt = null;
      state.phoneNumber = socket.user?.id || socket.user?.name || state.phoneNumber;
      state.lastError = null;
      state.reconnectAttempts = 0;
      logRuntime("instance_connected", {
        instance_id: instanceId,
        phone_number: state.phoneNumber,
      });
    }

    if (update.connection === "close") {
      const statusCode = update.lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      state.status = shouldReconnect ? "disconnected" : "logged_out";
      state.disconnectedAt = nowIso();
      state.lastError = update.lastDisconnect?.error?.message || null;
      state.socket = null;
      logRuntime("instance_connection_closed", {
        instance_id: instanceId,
        status_code: statusCode || null,
        should_reconnect: shouldReconnect,
        reconnect_attempts: state.reconnectAttempts,
        error: state.lastError,
      });
      if (shouldReconnect && state.reconnectAttempts < 3) {
        state.reconnectAttempts += 1;
        setTimeout(() => {
          connectInstance(instanceId, { name: state.displayName, reconnect: true }).catch((error) => {
            state.lastError = error instanceof Error ? error.message : String(error);
            logRuntime("instance_reconnect_error", {
              instance_id: instanceId,
              error: state.lastError,
            });
          });
        }, 1500);
      }
    }
  });

  return ok("Conexao Baileys iniciada. Aguarde QR Code ou status conectado.", publicState(state));
}

async function requestPairingCode(instanceId, body = {}) {
  const state = getState(instanceId);
  const phone = String(body.phone_number || body.phone || "").replace(/\D/g, "");
  if (!phone) {
    return fail("invalid_payload", "Telefone com codigo do pais e obrigatorio.", publicState(state));
  }

  if (!state.socket || !["connecting", "qr_required", "disconnected"].includes(state.status)) {
    await connectInstance(instanceId, { name: body.name || state.displayName || null });
  }

  if (!state.socket) {
    return fail("not_ready", "Socket Baileys ainda nao esta pronto para gerar codigo.", publicState(state));
  }

  if (state.socket.authState?.creds?.registered) {
    return fail("already_registered", "Instancia Baileys ja esta registrada.", publicState(state));
  }

  try {
    const code = await state.socket.requestPairingCode(phone);
    state.pairingCode = code;
    state.status = "qr_required";
    state.lastSeenAt = nowIso();
    state.lastError = null;
    logRuntime("instance_pairing_code_ready", {
      instance_id: instanceId,
      phone_number: phone,
      code_length: code.length,
    });
    return ok("Codigo de pareamento gerado.", {
      ...publicState(state),
      pairing_code: code,
      phone_number: phone,
    });
  } catch (error) {
    state.lastError = error instanceof Error ? error.message : String(error);
    logRuntime("instance_pairing_code_error", {
      instance_id: instanceId,
      phone_number: phone,
      error: state.lastError,
    });
    return fail("pairing_code_error", "Nao foi possivel gerar codigo de pareamento.", publicState(state));
  }
}

async function disconnectInstance(instanceId) {
  const state = getState(instanceId);
  if (state.socket) {
    await state.socket.logout().catch(() => undefined);
    state.socket.end?.(new Error("manual disconnect"));
  }
  state.socket = null;
  state.status = "disconnected";
  state.disconnectedAt = nowIso();
  state.lastSeenAt = nowIso();
  state.qrCode = null;
  state.qrCodeDataUrl = null;
  state.pairingCode = null;
  return ok("Instancia Baileys desconectada.", publicState(state));
}

async function deleteInstance(instanceId) {
  const state = getState(instanceId);
  if (state.socket) {
    await state.socket.logout().catch(() => undefined);
    state.socket.end?.(new Error("instance deleted"));
  }

  const sessionDir = path.join(dataDir, "sessions", instanceId);
  await fs.rm(sessionDir, { recursive: true, force: true });
  instances.delete(instanceId);
  logRuntime("instance_deleted", { instance_id: instanceId, session_dir: sessionDir });
  return ok("Instancia Baileys removida do runtime.", {
    instance_id: instanceId,
    status: "deleted",
    session_deleted: true,
  });
}

async function restartInstance(instanceId, body = {}) {
  await disconnectInstance(instanceId);
  return connectInstance(instanceId, body);
}

async function sendTextMessage(instanceId, body = {}) {
  const state = getState(instanceId);
  const connectionError = assertConnected(state);
  if (connectionError) return connectionError;

  const jid = normalizePhoneJid(body.phone);
  const text = String(body.text || "").trim();
  if (!jid || !text) {
    return fail("invalid_payload", "Telefone e texto sao obrigatorios.", publicState(state));
  }

  const result = await state.socket.sendMessage(jid, { text });
  state.lastSeenAt = nowIso();
  logRuntime("message_text_sent", {
    instance_id: instanceId,
    phone: String(body.phone || ""),
    normalized_phone: jidToPhone(jid),
    provider_message_id: result?.key?.id || null,
    remote_jid: result?.key?.remoteJid || jid,
  });
  return ok("Mensagem de texto enviada pela Baileys.", {
    ...publicState(state),
    status: "sent",
    provider_message_id: result?.key?.id || null,
    remote_jid: result?.key?.remoteJid || jid,
    normalized_phone: jidToPhone(jid),
  });
}

async function sendMediaMessage(instanceId, body = {}) {
  const state = getState(instanceId);
  const connectionError = assertConnected(state);
  if (connectionError) return connectionError;

  const jid = normalizePhoneJid(body.phone);
  const mediaUrl = String(body.media_url || "").trim();
  if (!jid || !mediaUrl) {
    return fail("invalid_payload", "Telefone e URL da midia sao obrigatorios.", publicState(state));
  }

  const mediaType = String(body.media_type || "").trim().toLowerCase();
  const caption = String(body.caption || "").trim() || undefined;
  const media = mediaReference(mediaUrl);
  const payload =
    mediaType === "audio"
      ? {
          audio: media,
          mimetype: body.mimetype || "audio/ogg; codecs=opus",
          ptt: body.ptt !== false,
        }
      : mediaType === "video"
      ? { video: media, caption }
      : mediaType === "document"
        ? {
            document: media,
            fileName: body.file_name || "arquivo",
            mimetype: body.mimetype || "application/octet-stream",
            caption,
          }
        : { image: media, caption };

  const result = await state.socket.sendMessage(jid, payload);
  state.lastSeenAt = nowIso();
  logRuntime("message_media_sent", {
    instance_id: instanceId,
    phone: String(body.phone || ""),
    normalized_phone: jidToPhone(jid),
    provider_message_id: result?.key?.id || null,
    remote_jid: result?.key?.remoteJid || jid,
  });
  return ok("Mensagem de midia enviada pela Baileys.", {
    ...publicState(state),
    status: "sent",
    provider_message_id: result?.key?.id || null,
    remote_jid: result?.key?.remoteJid || jid,
    normalized_phone: jidToPhone(jid),
  });
}

async function route(request, response) {
  if (!assertAuthorized(request)) {
    return sendJson(response, 401, fail("unauthorized", "Token do runtime invalido."));
  }

  const url = new URL(request.url || "/", `http://${host}:${port}`);
  const parts = url.pathname.split("/").filter(Boolean);

  if (request.method === "GET" && url.pathname === "/health") {
    return sendJson(response, 200, ok("Runtime Baileys ativo.", {
      status: "online",
      host,
      port,
      data_dir: dataDir,
      active_instances: [...instances.values()].filter((item) => item.socket).length,
      backend_event_url: backendEventUrl,
    }));
  }

  if (parts[0] !== "instances" || !parts[1]) {
    return sendJson(response, 404, fail("not_found", "Rota nao encontrada."));
  }

  const instanceId = decodeURIComponent(parts[1]);
  const action = parts[2];

  if (request.method === "POST" && action === "connect") {
    return sendJson(response, 200, await connectInstance(instanceId, await readBody(request)));
  }

  if (request.method === "GET" && action === "qrcode") {
    const state = getState(instanceId);
    return sendJson(response, 200, ok("QR Code consultado.", publicState(state)));
  }

  if (request.method === "POST" && action === "pairing-code") {
    return sendJson(response, 200, await requestPairingCode(instanceId, await readBody(request)));
  }

  if (request.method === "GET" && action === "status") {
    const state = getState(instanceId);
    return sendJson(response, 200, ok("Status consultado.", publicState(state)));
  }

  if (request.method === "POST" && action === "disconnect") {
    return sendJson(response, 200, await disconnectInstance(instanceId));
  }

  if (request.method === "DELETE" && !action) {
    return sendJson(response, 200, await deleteInstance(instanceId));
  }

  if (request.method === "POST" && action === "restart") {
    return sendJson(response, 200, await restartInstance(instanceId, await readBody(request)));
  }

  if (request.method === "POST" && action === "messages" && parts[3] === "text") {
    return sendJson(response, 200, await sendTextMessage(instanceId, await readBody(request)));
  }

  if (request.method === "POST" && action === "messages" && parts[3] === "media") {
    return sendJson(response, 200, await sendMediaMessage(instanceId, await readBody(request)));
  }

  return sendJson(response, 404, fail("not_found", "Acao da instancia nao encontrada."));
}

await fs.mkdir(path.join(dataDir, "sessions"), { recursive: true });

const server = http.createServer((request, response) => {
  route(request, response).catch((error) => {
    sendJson(response, 500, fail("runtime_error", error instanceof Error ? error.message : String(error)));
  });
});

server.listen(port, host, () => {
  console.log(`WhatsApp Gateway Runtime listening on http://${host}:${port}`);
});
