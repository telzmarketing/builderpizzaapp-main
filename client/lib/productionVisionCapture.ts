export const PRODUCTION_CAPTURE_CHECKLIST = [
  { id: "start", label: "Foto início", stage: "dispatch_start" },
  { id: "pizza_ready", label: "Fotografia pizza pronta", stage: "pizza_ready" },
  { id: "box_closed", label: "Caixa fechada", stage: "box_closed" },
] as const;

export type ProductionCaptureStepId = (typeof PRODUCTION_CAPTURE_CHECKLIST)[number]["id"];
export type ProductionCaptureState = "not_started" | "countdown" | "pending" | "ok" | "unsupported" | "error";
export interface ProductionCaptureRule { stationId: string; enabled: boolean; automatic: boolean; delaySeconds: number; milestoneSeconds?: [number, number, number]; }
export interface ProductionCaptureResult { status?: unknown; original_storage_key?: string | null; [key: string]: unknown; }

const STORAGE_KEY = "production_vision_capture_rules";
const DEFAULT_RULE: Omit<ProductionCaptureRule, "stationId"> = { enabled: true, automatic: true, delaySeconds: 10 };

export function defaultProductionCaptureRule(stationId: string): ProductionCaptureRule {
  const isDispatch = stationId === "expedicao";
  return { stationId, ...DEFAULT_RULE, milestoneSeconds: isDispatch ? [5, 40, 0] : [10, 40, 0] };
}

export function readProductionCaptureRules(storage: Pick<Storage, "getItem"> | null = typeof window === "undefined" ? null : window.localStorage): Record<string, ProductionCaptureRule> {
  if (!storage) return {};
  try {
    const raw = JSON.parse(storage.getItem(STORAGE_KEY) || "{}") as Record<string, Partial<ProductionCaptureRule>>;
    return Object.fromEntries(Object.entries(raw).map(([stationId, value]) => [stationId, {
      ...defaultProductionCaptureRule(stationId),
      ...value,
      stationId,
      delaySeconds: Math.max(1, Math.min(3600, Number(value.delaySeconds) || DEFAULT_RULE.delaySeconds)),
    }]));
  } catch { return {}; }
}

export function writeProductionCaptureRules(rules: Record<string, ProductionCaptureRule>, storage: Pick<Storage, "setItem"> | null = typeof window === "undefined" ? null : window.localStorage) {
  if (!storage) return;
  storage.setItem(STORAGE_KEY, JSON.stringify(rules));
}

export function normalizeProductionCaptureState(value: unknown): Exclude<ProductionCaptureState, "not_started" | "countdown" | "error"> {
  const status = typeof value === "string" ? value.toLowerCase() : "";
  if (["unsupported", "unavailable", "not_supported"].includes(status)) return "unsupported";
  if (["pending", "queued", "processing", "accepted", "active", "partial"].includes(status)) return "pending";
  return ["ok", "captured", "processed", "complete", "completed", "confirmed", "success"].includes(status) ? "ok" : "pending";
}

export function captureResultState(result: ProductionCaptureResult): Exclude<ProductionCaptureState, "not_started" | "countdown" | "error"> {
  if (result.original_storage_key) return "ok";
  return normalizeProductionCaptureState(result.status);
}

export function getProductionCaptureBridge(): { capture: (input: { productionUnitId: string; stationId: string; stepId: string; stage: string }) => Promise<ProductionCaptureResult> } | null {
  const candidate = (globalThis as typeof globalThis & { telzProductionVisionCapture?: unknown }).telzProductionVisionCapture;
  if (!candidate || typeof candidate !== "object" || typeof (candidate as { capture?: unknown }).capture !== "function") return null;
  return candidate as { capture: (input: { productionUnitId: string; stationId: string; stepId: string; stage: string }) => Promise<ProductionCaptureResult> };
}
