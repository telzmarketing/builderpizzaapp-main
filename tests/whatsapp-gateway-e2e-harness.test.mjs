import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const script = await readFile(new URL("../scripts/whatsapp-gateway-e2e.mjs", import.meta.url), "utf8");

test("E2E harness requires an existing authenticated session and explicit inbound reply", () => {
  assert.match(script, /sessions.*creds\.json/);
  assert.match(script, /Sessao autenticada ausente/);
  assert.match(script, /--expect-reply/);
  assert.match(script, /message_received/);
  assert.match(script, /x-whatsapp-gateway-token/);
  assert.match(script, /provider_message_id/);
});

test("E2E harness launches only a loopback runtime and does not configure credentials", () => {
  assert.match(script, /127\.0\.0\.1/);
  assert.match(script, /backend-event-url/);
  assert.match(script, /nao cria QR nem credenciais/);
  assert.match(script, /child\.kill\("SIGTERM"\)/);
  assert.doesNotMatch(script, /writeFile\([^)]*creds/);
});
