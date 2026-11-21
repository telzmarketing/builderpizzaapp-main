import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";

function withTimeout(promise, timeoutMs) {
  if (!timeoutMs || timeoutMs <= 0) return promise;
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("Backend callback timeout.")), timeoutMs);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

export function createPersistentCallbackQueue({
  filePath,
  deliver,
  timeoutMs = 10_000,
  retryDelayMs = 1_000,
  fsModule = fs,
} = {}) {
  if (!filePath || typeof deliver !== "function") throw new TypeError("filePath e deliver sao obrigatorios.");

  let entries = [];
  let loaded = false;
  let loading = null;
  let stopped = false;
  let pumping = null;
  let wakeTimer = null;
  let mutation = Promise.resolve();

  const serialize = (operation) => {
    const next = mutation.then(operation, operation);
    mutation = next.catch(() => {});
    return next;
  };

  async function persist(nextEntries = entries) {
    await fsModule.mkdir(path.dirname(filePath), { recursive: true, mode: 0o700 });
    const temporaryPath = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
    await fsModule.writeFile(temporaryPath, JSON.stringify(nextEntries, null, 2), { encoding: "utf8", mode: 0o600 });
    await fsModule.rename(temporaryPath, filePath);
  }

  async function load() {
    if (loaded) return;
    if (!loading) loading = (async () => {
      try {
        const content = await fsModule.readFile(filePath, "utf8");
        const parsed = JSON.parse(content);
        if (!Array.isArray(parsed) || parsed.some((entry) => !entry?.id || !entry?.payload)) {
          throw new Error("Fila de callbacks invalida; arquivo preservado.");
        }
        entries = parsed;
      } catch (error) {
        if (error?.code !== "ENOENT") throw error;
      }
      loaded = true;
    })().finally(() => { loading = null; });
    return loading;
  }

  function armRetry() {
    if (stopped || wakeTimer) return;
    wakeTimer = setTimeout(() => {
      wakeTimer = null;
      pump().catch(() => {});
    }, retryDelayMs);
  }

  async function pump() {
    await load();
    if (stopped || pumping || !entries.length) return;
    pumping = (async () => {
      const entry = entries[0];
      try {
        await withTimeout(deliver(entry.payload), timeoutMs);
        await serialize(async () => {
          if (entries[0]?.id === entry.id) {
            const remaining = entries.slice(1);
            await persist(remaining);
            entries = remaining;
          }
        });
      } catch (error) {
        await serialize(async () => {
          if (entries[0]?.id === entry.id) {
            entries[0] = { ...entries[0], attempts: Number(entries[0].attempts || 0) + 1, last_error: String(error?.message || error) };
            await persist();
          }
        });
        armRetry();
      }
    })().finally(() => {
      pumping = null;
      if (!stopped && entries.length && !wakeTimer) pump().catch(() => {});
    });
    return pumping;
  }

  return {
    async start() {
      await load();
      pump().catch(() => {});
    },
    async enqueue(payload) {
      await load();
      await serialize(async () => {
        const next = [...entries, { id: randomUUID(), payload, attempts: 0, enqueued_at: new Date().toISOString() }];
        await persist(next);
        entries = next;
      });
      await pump();
    },
    async idle() {
      await mutation;
      if (pumping) await pumping;
      await mutation;
    },
    snapshot() {
      return entries.map((entry) => ({ ...entry }));
    },
    stop() {
      stopped = true;
      if (wakeTimer) clearTimeout(wakeTimer);
      wakeTimer = null;
    },
  };
}
