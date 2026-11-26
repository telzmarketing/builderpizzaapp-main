import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { createPersistentCallbackQueue } from "../server/whatsapp-gateway-events.mjs";

test("callback queue persists failed delivery, retries, and acknowledges only on success", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-events-"));
  const filePath = path.join(directory, "callbacks.json");
  let attempts = 0;
  const delivered = [];
  const queue = createPersistentCallbackQueue({
    filePath,
    retryDelayMs: 5,
    timeoutMs: 50,
    deliver: async (payload) => {
      attempts += 1;
      if (attempts === 1) throw new Error("temporary backend failure");
      delivered.push(payload);
    },
  });

  await queue.enqueue({ event_type: "message_received", instance_id: "wa-1", message: { id: "m-1" } });
  await new Promise((resolve) => setTimeout(resolve, 20));
  await queue.idle();

  assert.equal(attempts, 2);
  assert.deepEqual(delivered[0].message, { id: "m-1" });
  assert.deepEqual(JSON.parse(await readFile(filePath, "utf8")), []);
  queue.stop();
  await rm(directory, { recursive: true, force: true });
});

test("simulated Baileys callback is serialized and not lost when the first backend attempt times out", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-timeout-"));
  const filePath = path.join(directory, "callbacks.json");
  const socket = new EventEmitter();
  let calls = 0;
  const queue = createPersistentCallbackQueue({
    filePath,
    retryDelayMs: 5,
    timeoutMs: 10,
    deliver: async (payload) => {
      calls += 1;
      if (calls === 1) await new Promise((resolve) => setTimeout(resolve, 30));
      assert.equal(payload.instance_id, "wa-2");
    },
  });
  socket.on("messages.upsert", ({ messages }) => {
    for (const message of messages) queue.enqueue({ instance_id: "wa-2", message }).catch(() => {});
  });

  socket.emit("messages.upsert", { messages: [{ key: { id: "m-2" } }] });
  await viIdle(queue, () => calls >= 2);

  assert.equal(calls, 2);
  assert.deepEqual(JSON.parse(await readFile(filePath, "utf8")), []);
  queue.stop();
  await rm(directory, { recursive: true, force: true });
});

test("concurrent startup/enqueue preserves recovered callbacks and each new message", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-recover-"));
  const filePath = path.join(directory, "callbacks.json");
  const fsModule = await import("node:fs/promises");
  await fsModule.writeFile(filePath, JSON.stringify([{ id: "recovered", payload: { message: { id: "old" } } }]));
  const delivered = [];
  let releaseLoad;
  const loadBarrier = new Promise((resolve) => { releaseLoad = resolve; });
  const queue = createPersistentCallbackQueue({
    filePath,
    fsModule: { ...fsModule, async readFile(...args) { await loadBarrier; return fsModule.readFile(...args); } },
    deliver: async (payload) => { delivered.push(payload.message.id); },
  });
  const start = queue.start();
  const enqueue = queue.enqueue({ message: { id: "new" } });
  releaseLoad();
  await Promise.all([start, enqueue]);
  await viIdle(queue, () => delivered.length === 2);
  assert.deepEqual(delivered, ["old", "new"]);
  queue.stop();
  await rm(directory, { recursive: true, force: true });
});

async function viIdle(queue, predicate) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    await queue.idle();
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  assert.fail("callback queue did not drain");
}

test("connectInstance shares socket creation and manual disconnect remains terminal for old socket callbacks", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-runtime-"));
  process.env.WHATSAPP_GATEWAY_RUNTIME_TEST = "1";
  process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR = directory;
  const runtime = await import(`../server/whatsapp-gateway-runtime.mjs?test=${Date.now()}`);
  let factoryCalls = 0;
  const sent = [];
  let socket;
  runtime.__runtimeTest.setDependencies({
    fetchVersion: async () => ({ version: undefined }),
    authState: async () => ({ state: { creds: { registered: false } }, saveCreds() {} }),
    makeSocket: () => {
      factoryCalls += 1;
      socket = Object.assign(new EventEmitter(), {
        ev: new EventEmitter(),
        user: { id: "5511999999999@s.whatsapp.net" },
        end() {},
        async sendMessage(jid, message) {
          sent.push({ jid, message });
          return { key: { id: "simulated-outbound", remoteJid: jid } };
        },
      });
      return socket;
    },
  });

  const first = runtime.__runtimeTest.connectInstance("wa-race", { tenant_id: "tenant-a" });
  const second = runtime.__runtimeTest.connectInstance("wa-race", { tenant_id: "tenant-a" });
  await Promise.all([first, second]);
  assert.equal(factoryCalls, 1);
  socket.ev.emit("connection.update", { connection: "open" });
  const result = await runtime.__runtimeTest.sendTextMessage("wa-race", { phone: "5511999999999", text: "Teste local" });
  assert.equal(result.ok, true);
  assert.equal(result.data.provider_message_id, "simulated-outbound");
  assert.deepEqual(sent, [{ jid: "5511999999999@s.whatsapp.net", message: { text: "Teste local" } }]);
  const pendingQr = socket.ev.listeners("connection.update")[0]({ qr: "pending-qr" });
  await runtime.__runtimeTest.disconnectInstance("wa-race");
  await pendingQr;
  assert.equal(runtime.__runtimeTest.getState("wa-race").qrCodeDataUrl, null);
  const registry = JSON.parse(await readFile(path.join(directory, "instances.json"), "utf8"));
  assert.equal(registry[0].manual_stop, true);
  socket.ev.emit("connection.update", { connection: "open" });
  assert.equal(runtime.__runtimeTest.getState("wa-race").status, "disconnected");
  assert.equal(runtime.__runtimeTest.getState("wa-race").tenantId, "tenant-a");

  await rm(directory, { recursive: true, force: true });
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_TEST;
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR;
});

test("send failure marks the live instance disconnected and schedules recovery", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-send-failure-"));
  process.env.WHATSAPP_GATEWAY_RUNTIME_TEST = "1";
  process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR = directory;
  const runtime = await import(`../server/whatsapp-gateway-runtime.mjs?failure=${Date.now()}`);
  let socket;
  runtime.__runtimeTest.setDependencies({
    fetchVersion: async () => ({ version: undefined }),
    authState: async () => ({ state: { creds: { registered: true } }, saveCreds() {} }),
    makeSocket: () => {
      socket = Object.assign(new EventEmitter(), {
        ev: new EventEmitter(),
        end() {},
        async sendMessage() { throw new Error("socket write failed"); },
      });
      return socket;
    },
  });

  await runtime.__runtimeTest.connectInstance("wa-failure", { tenant_id: "tenant-a" });
  socket.ev.emit("connection.update", { connection: "open" });
  const result = await runtime.__runtimeTest.sendTextMessage("wa-failure", { phone: "5511999999999", text: "Teste" });

  assert.equal(result.ok, false);
  assert.equal(result.status, "send_failed");
  assert.equal(runtime.__runtimeTest.getState("wa-failure").status, "disconnected");
  assert.equal(runtime.__runtimeTest.getState("wa-failure").reconnectAttempts, 1);
  await runtime.__runtimeTest.disconnectInstance("wa-failure");
  await rm(directory, { recursive: true, force: true });
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_TEST;
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR;
});

test("failed socket bootstrap leaves the instance disconnected and schedules recovery", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-bootstrap-failure-"));
  process.env.WHATSAPP_GATEWAY_RUNTIME_TEST = "1";
  process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR = directory;
  const runtime = await import(`../server/whatsapp-gateway-runtime.mjs?bootstrap=${Date.now()}`);
  runtime.__runtimeTest.setDependencies({
    fetchVersion: async () => ({ version: undefined }),
    authState: async () => { throw new Error("auth store unavailable"); },
    makeSocket: () => { throw new Error("must not create socket"); },
  });

  const result = await runtime.__runtimeTest.connectInstance("wa-bootstrap", { tenant_id: "tenant-a" });
  const state = runtime.__runtimeTest.getState("wa-bootstrap");
  assert.equal(result.ok, false);
  assert.equal(result.status, "connect_failed");
  assert.equal(state.status, "disconnected");
  assert.equal(state.lastError, "auth store unavailable");
  assert.equal(state.reconnectAttempts, 1);

  await runtime.__runtimeTest.disconnectInstance("wa-bootstrap");
  await rm(directory, { recursive: true, force: true });
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_TEST;
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR;
});

test("a connected instance cannot be rebound to another tenant", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-tenant-binding-"));
  process.env.WHATSAPP_GATEWAY_RUNTIME_TEST = "1";
  process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR = directory;
  const runtime = await import(`../server/whatsapp-gateway-runtime.mjs?tenant=${Date.now()}`);
  runtime.__runtimeTest.setDependencies({
    fetchVersion: async () => ({ version: undefined }),
    authState: async () => ({ state: { creds: { registered: true } }, saveCreds() {} }),
    makeSocket: () => Object.assign(new EventEmitter(), {
      ev: new EventEmitter(),
      end() {},
    }),
  });

  await runtime.__runtimeTest.connectInstance("wa-bound", { tenant_id: "tenant-a" });
  const result = await runtime.__runtimeTest.connectInstance("wa-bound", { tenant_id: "tenant-b" });
  assert.equal(result.ok, false);
  assert.equal(result.status, "tenant_mismatch");
  assert.equal(runtime.__runtimeTest.getState("wa-bound").tenantId, "tenant-a");

  await runtime.__runtimeTest.disconnectInstance("wa-bound");
  await rm(directory, { recursive: true, force: true });
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_TEST;
  delete process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR;
});

test("messages.upsert is normalized and delivered to the tenant callback endpoint", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-inbound-"));
  process.env.WHATSAPP_GATEWAY_RUNTIME_TEST = "1";
  process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR = directory;
  const runtime = await import(`../server/whatsapp-gateway-runtime.mjs?inbound=${Date.now()}`);
  const callbacks = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    callbacks.push({ url, headers: options.headers, body: JSON.parse(options.body) });
    return { ok: true, async json() { return { ok: true, received: 1 }; } };
  };
  let socket;
  runtime.__runtimeTest.setDependencies({
    fetchVersion: async () => ({ version: undefined }),
    authState: async () => ({ state: { creds: { registered: true } }, saveCreds() {} }),
    makeSocket: () => {
      socket = Object.assign(new EventEmitter(), {
        ev: new EventEmitter(),
        end() {},
      });
      return socket;
    },
  });

  try {
    await runtime.__runtimeTest.connectInstance("wa-inbound", { tenant_id: "tenant-a", name: "Gateway A" });
    socket.ev.emit("messages.upsert", {
      messages: [{
        key: { id: "inbound-runtime-1", remoteJid: "5511999999999@s.whatsapp.net", fromMe: false },
        pushName: "Cliente A",
        message: { conversation: "Ola pelo WhatsApp" },
      }],
    });

    for (let attempt = 0; attempt < 100 && callbacks.length === 0; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
    assert.equal(callbacks.length, 1);
    assert.equal(callbacks[0].body.instance_id, "wa-inbound");
    assert.equal(callbacks[0].body.event_type, "message_received");
    assert.equal(callbacks[0].body.message.id, "inbound-runtime-1");
    assert.equal(callbacks[0].body.message.phone, "5511999999999");
    assert.equal(callbacks[0].body.message.body, "Ola pelo WhatsApp");
    assert.equal(callbacks[0].body.message.from_me, false);
  } finally {
    await runtime.__runtimeTest.disconnectInstance("wa-inbound");
    globalThis.fetch = originalFetch;
    await rm(directory, { recursive: true, force: true });
    delete process.env.WHATSAPP_GATEWAY_RUNTIME_TEST;
    delete process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR;
  }
});

test("messaging-history.set replays inbound history into the tenant callback endpoint", async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), "telz-wa-history-"));
  process.env.WHATSAPP_GATEWAY_RUNTIME_TEST = "1";
  process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR = directory;
  const runtime = await import(`../server/whatsapp-gateway-runtime.mjs?history=${Date.now()}`);
  const callbacks = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    callbacks.push({ url, headers: options.headers, body: JSON.parse(options.body) });
    return { ok: true, async json() { return { ok: true, received: 1 }; } };
  };
  let socket;
  runtime.__runtimeTest.setDependencies({
    fetchVersion: async () => ({ version: undefined }),
    authState: async () => ({ state: { creds: { registered: true } }, saveCreds() {} }),
    makeSocket: () => {
      socket = Object.assign(new EventEmitter(), {
        ev: new EventEmitter(),
        end() {},
      });
      return socket;
    },
  });

  try {
    await runtime.__runtimeTest.connectInstance("wa-history", { tenant_id: "tenant-a", name: "Gateway A" });
    socket.ev.emit("messaging-history.set", {
      messages: [{
        key: { id: "historical-inbound-1", remoteJid: "5511888888888@s.whatsapp.net", fromMe: false },
        pushName: "Cliente Historico",
        message: { conversation: "Mensagem do historico" },
      }],
    });

    for (let attempt = 0; attempt < 100 && callbacks.length === 0; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
    assert.equal(callbacks.length, 1);
    assert.equal(callbacks[0].body.event_type, "message_received");
    assert.equal(callbacks[0].body.message.id, "historical-inbound-1");
    assert.equal(callbacks[0].body.message.body, "Mensagem do historico");
    assert.equal(callbacks[0].body.payload.historical_sync, true);
  } finally {
    await runtime.__runtimeTest.disconnectInstance("wa-history");
    globalThis.fetch = originalFetch;
    await rm(directory, { recursive: true, force: true });
    delete process.env.WHATSAPP_GATEWAY_RUNTIME_TEST;
    delete process.env.WHATSAPP_GATEWAY_RUNTIME_DATA_DIR;
  }
});
