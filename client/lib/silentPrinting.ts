/** Client-only bridge for QZ Tray or an explicitly authorized local agent.
 * It never opens a window and never delegates to the browser print dialog.
 */

export type SilentPrintDocumentType = "receipt" | "pizza_label" | "ingredient_label" | "test" | "other";
export type SilentPrintContent = { kind: "html"; data: string } | { kind: "raw"; data: string | number[] };
export type SilentPrintStatus = "queued" | "sent" | "confirmed" | "error" | "agent_unavailable";
export type SilentPrintTransport = "auto" | "qz" | "local_agent";

export interface SilentPrintAgentConfig { transport: SilentPrintTransport; baseUrl: string; token?: string; requestTimeoutMs: number; }
export interface SilentPrintJobInput {
  documentId: string; documentType: SilentPrintDocumentType; content: SilentPrintContent;
  printerId?: string | null; printerName?: string | null;
  paper?: { widthMm?: number; heightMm?: number; paperWidth?: string };
  copies?: number; metadata?: Record<string, string | number | boolean | null | undefined>; idempotencyKey?: string;
}
export interface SilentPrintJobResult { jobId: string; status: Exclude<SilentPrintStatus, "queued">; transport: Exclude<SilentPrintTransport, "auto">; message?: string; agentVersion?: string; }

export class SilentPrintError extends Error {
  readonly code: "AGENT_UNAVAILABLE" | "AGENT_REJECTED" | "AGENT_TIMEOUT" | "DUPLICATE" | "INVALID_JOB";
  readonly jobId?: string;
  constructor(code: SilentPrintError["code"], message: string, jobId?: string) { super(message); this.name = "SilentPrintError"; this.code = code; this.jobId = jobId; }
}

type QzApi = { websocket: { isActive?: () => boolean; connect: () => Promise<void> }; configs: { create: (printer: string, options?: Record<string, unknown>) => unknown }; print: (config: unknown, data: unknown[]) => Promise<unknown>; printers?: { find: (name?: string) => Promise<string | string[]> } };
declare global { interface Window { qz?: QzApi } }

const CONFIG_KEY = "moschettieri_silent_print_agent";
const HISTORY_KEY = "moschettieri_silent_print_jobs";
const DEFAULT_CONFIG: SilentPrintAgentConfig = { transport: "auto", baseUrl: "http://127.0.0.1:18181", requestTimeoutMs: 2500 };
const inFlight = new Map<string, Promise<SilentPrintJobResult>>();

export function loadSilentPrintAgentConfig(): SilentPrintAgentConfig {
  try { const parsed = JSON.parse(localStorage.getItem(CONFIG_KEY) || "null") as Partial<SilentPrintAgentConfig> | null; return { ...DEFAULT_CONFIG, ...parsed, baseUrl: String(parsed?.baseUrl || DEFAULT_CONFIG.baseUrl).replace(/\/$/, ""), requestTimeoutMs: Math.max(500, Math.min(10000, Number(parsed?.requestTimeoutMs) || DEFAULT_CONFIG.requestTimeoutMs)) }; }
  catch { return { ...DEFAULT_CONFIG }; }
}
export function saveSilentPrintAgentConfig(config: Partial<SilentPrintAgentConfig>): SilentPrintAgentConfig { const next = { ...loadSilentPrintAgentConfig(), ...config }; try { localStorage.setItem(CONFIG_KEY, JSON.stringify(next)); } catch { /* optional setting */ } return next; }
function idFor(input: SilentPrintJobInput) { return input.idempotencyKey || `${input.documentType}:${input.documentId}`; }
function remember(result: SilentPrintJobResult, input: SilentPrintJobInput) { try { const current = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); const history = Array.isArray(current) ? current : []; localStorage.setItem(HISTORY_KEY, JSON.stringify([{ ...result, documentId: input.documentId, documentType: input.documentType, updatedAt: new Date().toISOString() }, ...history.filter((item) => item?.jobId !== result.jobId)].slice(0, 100))); } catch { /* advisory */ } }
export function getSilentPrintHistory() { try { const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); return Array.isArray(value) ? value : []; } catch { return []; } }
function qz(): QzApi | undefined { return typeof window !== "undefined" ? window.qz : undefined; }
export function detectSilentPrintTransport(config = loadSilentPrintAgentConfig()): "qz" | "local_agent" | null { if ((config.transport === "auto" || config.transport === "qz") && qz()) return "qz"; if (config.transport === "qz") return null; return config.transport === "local_agent" || config.transport === "auto" ? "local_agent" : null; }
async function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> { let timer: ReturnType<typeof globalThis.setTimeout> | undefined; try { return await Promise.race([promise, new Promise<T>((_, reject) => { timer = globalThis.setTimeout(() => reject(new SilentPrintError("AGENT_TIMEOUT", message)), ms); })]); } finally { if (timer) globalThis.clearTimeout(timer); } }

async function localAgent(input: SilentPrintJobInput, id: string, config: SilentPrintAgentConfig): Promise<SilentPrintJobResult> {
  const response = await withTimeout(fetch(`${config.baseUrl}/v1/print`, { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json", "Idempotency-Key": id, ...(config.token ? { Authorization: `Bearer ${config.token}` } : {}) }, body: JSON.stringify({ job_id: id, document_id: input.documentId, document_type: input.documentType, content: input.content, printer_id: input.printerId ?? null, printer_name: input.printerName ?? null, paper: input.paper ?? null, copies: Math.max(1, Math.min(20, Math.floor(input.copies || 1))), metadata: input.metadata ?? {} }) }), config.requestTimeoutMs, "O agente local não respondeu no tempo esperado.").catch((error) => { if (error instanceof SilentPrintError) throw error; throw new SilentPrintError("AGENT_UNAVAILABLE", "Agente local de impressão indisponível; nenhuma janela de impressão foi aberta.", id); });
  const body = await response.json().catch(() => ({}));
  if (response.status === 409) throw new SilentPrintError("DUPLICATE", "Trabalho já enviado; nova cópia ignorada.", id);
  if (!response.ok) throw new SilentPrintError("AGENT_REJECTED", body.message || `Agente recusou o trabalho (HTTP ${response.status}).`, id);
  return { jobId: String(body.job_id || id), status: body.status === "confirmed" ? "confirmed" : "sent", transport: "local_agent", message: body.message, agentVersion: body.agent_version };
}
async function qzPrint(input: SilentPrintJobInput, id: string): Promise<SilentPrintJobResult> {
  const api = qz(); if (!api) throw new SilentPrintError("AGENT_UNAVAILABLE", "QZ Tray não está disponível; nenhuma janela de impressão foi aberta.", id);
  try { if (!api.websocket.isActive?.()) await api.websocket.connect(); const printer = input.printerName || input.printerId; if (!printer) throw new SilentPrintError("INVALID_JOB", "Impressora não identificada para o trabalho.", id); const resolved = api.printers?.find ? await api.printers.find(printer) : printer; const selected = Array.isArray(resolved) ? resolved[0] : resolved; if (!selected) throw new SilentPrintError("AGENT_REJECTED", "QZ Tray não encontrou a impressora configurada.", id); const config = api.configs.create(selected, { copies: Math.max(1, Math.min(20, Math.floor(input.copies || 1))) }); const data = input.content.kind === "html" ? [{ type: "html", format: "plain", data: input.content.data }] : [{ type: "raw", format: "plain", data: input.content.data }]; await withTimeout(api.print(config, data), loadSilentPrintAgentConfig().requestTimeoutMs, "QZ Tray não confirmou o envio no tempo esperado."); return { jobId: id, status: "confirmed", transport: "qz", message: "QZ Tray aceitou o trabalho." }; }
  catch (error) { if (error instanceof SilentPrintError) throw error; throw new SilentPrintError("AGENT_REJECTED", error instanceof Error ? error.message : "QZ Tray recusou o trabalho.", id); }
}
export async function checkSilentPrintAgent(): Promise<{ available: boolean; transport: "qz" | "local_agent" | null; message?: string }> { const config = loadSilentPrintAgentConfig(); if (detectSilentPrintTransport(config) === "qz") return { available: true, transport: "qz" }; try { const response = await withTimeout(fetch(`${config.baseUrl}/v1/health`, { headers: config.token ? { Authorization: `Bearer ${config.token}` } : {} }), config.requestTimeoutMs, "Agente local não respondeu."); return { available: response.ok, transport: response.ok ? "local_agent" : null, message: response.ok ? undefined : `Agente respondeu HTTP ${response.status}.` }; } catch (error) { return { available: false, transport: null, message: error instanceof Error ? error.message : "Agente indisponível." }; } }
export function enqueueSilentPrint(input: SilentPrintJobInput): Promise<SilentPrintJobResult> { if (!input.documentId || !input.documentType || !input.content?.data) return Promise.reject(new SilentPrintError("INVALID_JOB", "Trabalho de impressão sem documento ou conteúdo.")); const id = idFor(input); const existing = inFlight.get(id); if (existing) return existing; const promise = (async () => { const config = loadSilentPrintAgentConfig(); const transport = detectSilentPrintTransport(config); if (!transport) throw new SilentPrintError("AGENT_UNAVAILABLE", "Nenhum agente autorizado está disponível; nenhuma janela de impressão foi aberta.", id); const result = transport === "qz" ? await qzPrint(input, id) : await localAgent(input, id, config); remember(result, input); return result; })().catch((error) => { if (error instanceof SilentPrintError) { if (["AGENT_UNAVAILABLE", "AGENT_TIMEOUT"].includes(error.code)) remember({ jobId: id, status: error.code === "AGENT_TIMEOUT" ? "error" : "agent_unavailable", transport: detectSilentPrintTransport(loadSilentPrintAgentConfig()) || "local_agent", message: error.message }, input); throw error; } throw new SilentPrintError("AGENT_REJECTED", "Falha inesperada no agente de impressão.", id); }).finally(() => inFlight.delete(id)); inFlight.set(id, promise); return promise; }
export function silentPrintFallbackMessage(error: unknown) { return error instanceof Error ? error.message : "Não foi possível enviar o trabalho para impressão direta."; }
