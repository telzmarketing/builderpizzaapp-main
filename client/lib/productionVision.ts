import { apiRequest } from "@/lib/api";

export type ProductionVisionStatus = "online" | "offline" | "active" | "completed" | "partial" | "failed" | string;
export interface ProductionVisionCamera { id: string; name: string; station_name?: string | null; status?: ProductionVisionStatus | null; last_connected_at?: string | null; }
export interface ProductionVisionStation { id: string; name: string; camera_count?: number | null; active_sessions?: number | null; status?: ProductionVisionStatus | null; }
export interface ProductionVisionSession { id: string; order_code?: string | null; product_name?: string | null; station_name?: string | null; status?: ProductionVisionStatus | null; started_at?: string | null; captured_photos?: number | null; }
export interface ProductionVisionHistoryItem { id: string; order_code?: string | null; product_name?: string | null; stage?: string | null; status?: ProductionVisionStatus | null; captured_at?: string | null; photo_count?: number | null; }
export interface ProductionVisionDashboard { cameras: ProductionVisionCamera[]; stations: ProductionVisionStation[]; sessions: ProductionVisionSession[]; history: ProductionVisionHistoryItem[]; metrics?: { monitored_orders?: number | null; completed_sessions?: number | null; partial_sessions?: number | null; photos_captured?: number | null; photos_processed?: number | null; } | null; }

function arrayOf<T>(value: unknown): T[] { return Array.isArray(value) ? value as T[] : []; }
function numberOrNull(value: unknown): number | null { return typeof value === "number" && Number.isFinite(value) ? value : null; }
export function normalizeProductionVisionDashboard(payload: unknown): ProductionVisionDashboard {
  const root = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
  const data = root.data && typeof root.data === "object" ? root.data as Record<string, unknown> : root;
  return { cameras: arrayOf<ProductionVisionCamera>(data.cameras ?? data.camera_list), stations: arrayOf<ProductionVisionStation>(data.stations ?? data.workstations ?? data.work_stations), sessions: arrayOf<ProductionVisionSession>(data.sessions ?? data.active_sessions), history: arrayOf<ProductionVisionHistoryItem>(data.history ?? data.photo_history ?? data.recent_history), metrics: data.metrics && typeof data.metrics === "object" ? data.metrics as ProductionVisionDashboard["metrics"] : null };
}
export const productionVisionApi = {
  dashboard: async (): Promise<ProductionVisionDashboard> => {
    const [summary, cameras, stations] = await Promise.all([
      apiRequest<unknown>("GET", "/production-vision/dashboard"),
      apiRequest<unknown>("GET", "/production-vision/cameras"),
      apiRequest<unknown>("GET", "/production-vision/stations"),
    ]);
    const summaryRoot = summary && typeof summary === "object" ? summary as Record<string, unknown> : {};
    const metrics = (summaryRoot.data && typeof summaryRoot.data === "object" ? summaryRoot.data : summaryRoot) as Record<string, unknown>;
    const cameraRoot = cameras && typeof cameras === "object" ? cameras as Record<string, unknown> : {};
    const stationRoot = stations && typeof stations === "object" ? stations as Record<string, unknown> : {};
    return {
      cameras: arrayOf<ProductionVisionCamera>(cameraRoot.data ?? cameraRoot),
      stations: arrayOf<ProductionVisionStation>(stationRoot.data ?? stationRoot),
      sessions: [],
      history: [],
      metrics: {
        monitored_orders: numberOrNull(metrics.sessions_active),
        completed_sessions: numberOrNull(metrics.sessions_complete),
        partial_sessions: numberOrNull(metrics.sessions_partial),
        photos_captured: numberOrNull(metrics.photos_captured),
        photos_processed: null,
      },
    };
  },
};
