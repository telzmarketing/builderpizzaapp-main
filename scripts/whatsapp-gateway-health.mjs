import process from "node:process";

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  const key = process.argv[index];
  const value = process.argv[index + 1];
  if (key?.startsWith("--")) args.set(key.slice(2), value);
}

const baseUrl = (
  args.get("url") ||
  process.env.WHATSAPP_GATEWAY_RUNTIME_URL ||
  "http://127.0.0.1:3020"
).replace(/\/+$/, "");
const token = args.get("token") || process.env.WHATSAPP_GATEWAY_RUNTIME_TOKEN || "";
const timeoutMs = Number(args.get("timeout-ms") || process.env.WHATSAPP_GATEWAY_HEALTH_TIMEOUT_MS || 5000);

const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), timeoutMs);

try {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${baseUrl}/health`, { headers, signal: controller.signal });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok !== true || payload.data?.status !== "online") {
    console.error(JSON.stringify({ ok: false, http_status: response.status, payload }));
    process.exit(1);
  }
  console.log(JSON.stringify({ ok: true, runtime_url: baseUrl, data: payload.data }));
} catch (error) {
  console.error(JSON.stringify({ ok: false, runtime_url: baseUrl, error: error instanceof Error ? error.message : String(error) }));
  process.exit(1);
} finally {
  clearTimeout(timer);
}
