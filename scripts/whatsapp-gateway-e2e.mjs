#!/usr/bin/env node

import { existsSync } from "node:fs";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const runtimePath = path.join(root, "server", "whatsapp-gateway-runtime.mjs");

function parseArgs(argv = process.argv.slice(2)) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith("--")) continue;
    const key = item.slice(2).replaceAll("-", "_");
    if (key === "help") {
      result.help = true;
      continue;
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) throw new Error(`Valor ausente para --${key.replaceAll("_", "-")}.`);
    result[key] = value;
    index += 1;
  }
  return result;
}

function usage() {
  return `Uso seguro (somente com uma sessao Baileys ja autenticada):

  node scripts/whatsapp-gateway-e2e.mjs \\
    --data-dir /caminho/para/.runtime/baileys \\
    --instance-id principal \\
    --tenant-id tenant-id \\
    --to 5511999999999 \\
    --from 5511888888888 \\
    --expect-reply "resposta de teste"

O script inicia apenas um runtime local temporario, envia uma mensagem explicita
e aguarda o callback message_received correspondente. Ele nao cria QR, nao salva
credenciais, nao configura tokens e nao altera deploy. A resposta deve ser enviada
manualmente pelo contato informado em --from dentro do prazo de --timeout-ms.`;
}

function normalizePhone(value) {
  const digits = String(value || "").replace(/\D/g, "");
  return digits.startsWith("55") ? digits : `55${digits}`;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function requestJson(baseUrl, method, pathname, { token = "", body, timeoutMs = 5000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}${pathname}`, {
      method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body === undefined ? {} : { "content-type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: controller.signal,
    });
    const payload = await response.json().catch(() => ({}));
    return { response, payload };
  } finally {
    clearTimeout(timer);
  }
}

async function waitFor(predicate, { timeoutMs, intervalMs = 500, description }) {
  const deadline = Date.now() + timeoutMs;
  let lastValue;
  while (Date.now() < deadline) {
    lastValue = await predicate();
    if (lastValue) return lastValue;
    await sleep(intervalMs);
  }
  throw new Error(`Tempo esgotado aguardando ${description}.`);
}

function startCallbackSink(eventToken, received) {
  const server = createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/health") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: true }));
      return;
    }
    if (request.method !== "POST" || request.url !== "/events") {
      response.writeHead(404);
      response.end();
      return;
    }
    if (request.headers["x-whatsapp-gateway-token"] !== eventToken) {
      response.writeHead(401);
      response.end(JSON.stringify({ ok: false }));
      return;
    }
    let raw = "";
    for await (const chunk of request) raw += chunk;
    try {
      const payload = JSON.parse(raw);
      if (payload?.event_type === "message_received") received.push(payload);
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: true, received: 1 }));
    } catch {
      response.writeHead(400);
      response.end(JSON.stringify({ ok: false }));
    }
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.removeListener("error", reject);
      const address = server.address();
      resolve({ server, url: `http://127.0.0.1:${address.port}` });
    });
  });
}

async function findFreePort() {
  const probe = createServer();
  return new Promise((resolve, reject) => {
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      probe.close((error) => (error ? reject(error) : resolve(address.port)));
    });
  });
}

function tail(lines, chunk) {
  lines.push(...String(chunk).split(/\r?\n/).filter(Boolean));
  while (lines.length > 20) lines.shift();
}

export async function runE2E(options = {}) {
  const dataDir = path.resolve(options.data_dir || process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR || "");
  const instanceId = String(options.instance_id || "").trim();
  const tenantId = String(options.tenant_id || "").trim();
  const to = normalizePhone(options.to);
  const from = normalizePhone(options.from);
  const expectedReply = String(options.expect_reply || "");
  const timeoutMs = Number(options.timeout_ms || 120000);
  const runtimeToken = String(options.runtime_token || process.env.WHATSAPP_GATEWAY_RUNTIME_TOKEN || "");

  if (!dataDir || !instanceId || !options.to || !options.from || !expectedReply) {
    throw new Error("--data-dir, --instance-id, --to, --from e --expect-reply sao obrigatorios.");
  }
  if (!existsSync(path.join(dataDir, "sessions", instanceId, "creds.json"))) {
    throw new Error("Sessao autenticada ausente: o harness nao cria QR nem credenciais.");
  }

  const received = [];
  const eventToken = randomUUID();
  const sink = await startCallbackSink(eventToken, received);
  const port = Number(options.port || await findFreePort());
  const runtimeArgs = [
    runtimePath,
    "--host", "127.0.0.1",
    "--port", String(port || 0),
    "--data-dir", dataDir,
    "--backend-event-url", `${sink.url}/events`,
    "--event-token", eventToken,
    ...(runtimeToken ? ["--token", runtimeToken] : []),
  ];
  const logs = [];
  const child = spawn(process.execPath, runtimeArgs, { cwd: root, stdio: ["ignore", "pipe", "pipe"] });
  child.stdout.on("data", (chunk) => tail(logs, chunk));
  child.stderr.on("data", (chunk) => tail(logs, chunk));

  let baseUrl;
  try {
    baseUrl = `http://127.0.0.1:${port}`;
    await waitFor(async () => {
      try {
        const result = await requestJson(baseUrl, "GET", "/health", { token: runtimeToken, timeoutMs: 1000 });
        return result.payload?.ok === true ? result : false;
      } catch {
        return false;
      }
    }, { timeoutMs: 15000, intervalMs: 250, description: "runtime Baileys local" });

    const connect = await requestJson(baseUrl, "POST", `/instances/${encodeURIComponent(instanceId)}/connect`, {
      token: runtimeToken,
      body: tenantId ? { tenant_id: tenantId, name: "E2E WhatsApp" } : { name: "E2E WhatsApp" },
    });
    if (connect.payload?.ok !== true) throw new Error(`Falha ao conectar instancia: ${JSON.stringify(connect.payload)}`);

    const status = await waitFor(async () => {
      const result = await requestJson(baseUrl, "GET", `/instances/${encodeURIComponent(instanceId)}/status`, { token: runtimeToken });
      const state = result.payload?.data || result.payload?.runtime || {};
      if (state.status === "connected") return state;
      if (state.status === "qr_required" || state.status === "logged_out") {
        throw new Error(`Sessao nao autenticada; status atual: ${state.status}.`);
      }
      return false;
    }, { timeoutMs, intervalMs: 500, description: "sessao WhatsApp autenticada" });

    const text = String(options.text || `Telz E2E ${new Date().toISOString()}`);
    const sent = await requestJson(baseUrl, "POST", `/instances/${encodeURIComponent(instanceId)}/messages/text`, {
      token: runtimeToken,
      body: { phone: to, text },
    });
    if (sent.payload?.ok !== true || sent.payload?.data?.status !== "sent") {
      throw new Error(`Falha no envio real: ${JSON.stringify(sent.payload)}`);
    }

    const inbound = await waitFor(() => received.find((event) => {
      const message = event.message || {};
      return normalizePhone(message.phone) === from && String(message.body || "") === expectedReply;
    }), { timeoutMs, intervalMs: 500, description: `resposta inbound de ${from}` });

    return {
      ok: true,
      instance_id: instanceId,
      connected_status: status.status,
      outbound: {
        phone: to,
        text,
        provider_message_id: sent.payload.data.provider_message_id || null,
      },
      inbound: {
        phone: inbound.message.phone,
        body: inbound.message.body,
        provider_message_id: inbound.message.id,
      },
    };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`${detail}${logs.length ? `\nRuntime:\n${logs.join("\n")}` : ""}`);
  } finally {
    sink.server.close();
    child.kill("SIGTERM");
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const options = parseArgs();
    if (options.help) {
      console.log(usage());
      process.exit(0);
    }
    console.log(JSON.stringify(await runE2E(options), null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }));
    process.exit(1);
  }
}
