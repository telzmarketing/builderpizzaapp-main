import { apiRequest } from "@/lib/api";

export type ProductionVisionStatus = "online" | "offline" | "active" | "inactive" | "completed" | "complete" | "partial" | "failed" | string;
export interface ProductionVisionCamera { id: string; name: string; identifier?: string | null; station_id?: string | null; station_name?: string | null; manufacturer?: string | null; model?: string | null; ip_address?: string | null; port?: number | null; protocol?: string | null; resolution?: string | null; orientation?: string | null; installation_height_cm?: number | null; status?: ProductionVisionStatus | null; last_connected_at?: string | null; has_credentials?: boolean; }
export type ProductionVisionCameraInput = Omit<ProductionVisionCamera, "id" | "station_name" | "last_connected_at" | "has_credentials"> & { name: string; identifier: string; station_id: string; password?: string; connection_url?: string; username?: string; };
export interface ProductionVisionStation { id: string; name: string; identifier?: string | null; station_type?: string | null; fixed?: boolean; protected?: boolean; camera_count?: number | null; active_sessions?: number | null; status?: ProductionVisionStatus | null; }
export type ProductionVisionStationInput = { name: string; identifier: string; status?: "active" | "inactive" };
export interface ProductionVisionZone { id: string; identifier: string; name: string; station_id: string; camera_id?: string | null; status?: "active" | "inactive" | string; occupied?: boolean; }
export type ProductionVisionZoneInput = Omit<ProductionVisionZone, "id" | "occupied"> & { exclusive?: boolean };
export interface ProductionVisionSession { id: string; production_unit_id?: string | null; order_code?: string | null; product_name?: string | null; station_name?: string | null; stage?: string | null; status?: ProductionVisionStatus | null; started_at?: string | null; captured_photos?: number | null; }
export interface ProductionVisionHistoryItem { id: string; order_code?: string | null; product_name?: string | null; stage?: string | null; status?: ProductionVisionStatus | null; captured_at?: string | null; photo_count?: number | null; }
export interface ProductionVisionMetrics { cameras_online?: number | null; cameras_offline?: number | null; sessions_active?: number | null; sessions_complete?: number | null; sessions_partial?: number | null; photos_captured?: number | null; monitored_orders?: number | null; completed_sessions?: number | null; partial_sessions?: number | null; photos_processed?: number | null; }
export interface ProductionVisionDashboard { cameras: ProductionVisionCamera[]; stations: ProductionVisionStation[]; zones: ProductionVisionZone[]; sessions: ProductionVisionSession[]; history: ProductionVisionHistoryItem[]; metrics: ProductionVisionMetrics | null; }

function record(value: unknown): Record<string, unknown> { return value && typeof value === "object" ? value as Record<string, unknown> : {}; }
function arrayOf<T>(value: unknown): T[] { return Array.isArray(value) ? value as T[] : []; }
function unwrap(value: unknown): Record<string, unknown> { const root = record(value); return record(root.data ?? root); }
function numberOrNull(value: unknown): number | null { return typeof value === "number" && Number.isFinite(value) ? value : null; }

export function normalizeProductionVisionDashboard(payload: unknown): ProductionVisionDashboard {
  const data = unwrap(payload); const rawMetrics = record(data.metrics); const metrics = Object.keys(rawMetrics).length ? rawMetrics : data;
  return { cameras: arrayOf<ProductionVisionCamera>(data.cameras ?? data.camera_list), stations: arrayOf<ProductionVisionStation>(data.stations ?? data.workstations ?? data.work_stations), zones: arrayOf<ProductionVisionZone>(data.zones), sessions: arrayOf<ProductionVisionSession>(data.sessions ?? data.active_sessions), history: arrayOf<ProductionVisionHistoryItem>(data.history ?? data.photo_history ?? data.recent_history), metrics: { cameras_online: numberOrNull(metrics.cameras_online), cameras_offline: numberOrNull(metrics.cameras_offline), sessions_active: numberOrNull(metrics.sessions_active), sessions_complete: numberOrNull(metrics.sessions_complete), sessions_partial: numberOrNull(metrics.sessions_partial), photos_captured: numberOrNull(metrics.photos_captured), monitored_orders: numberOrNull(metrics.monitored_orders ?? metrics.sessions_active), completed_sessions: numberOrNull(metrics.completed_sessions ?? metrics.sessions_complete), partial_sessions: numberOrNull(metrics.partial_sessions ?? metrics.sessions_partial), photos_processed: numberOrNull(metrics.photos_processed) } };
}
export function normalizeProductionVisionList<T>(payload: unknown): T[] { const root = record(payload); return arrayOf<T>(root.data ?? payload); }

export const productionVisionApi = {
  dashboard: async (): Promise<ProductionVisionDashboard> => { const [summary, cameras, stations, zones] = await Promise.all([apiRequest<unknown>("GET", "/production-vision/dashboard"), apiRequest<unknown>("GET", "/production-vision/cameras"), apiRequest<unknown>("GET", "/production-vision/stations"), apiRequest<unknown>("GET", "/production-vision/zones")]); const result = normalizeProductionVisionDashboard(summary); return { ...result, cameras: normalizeProductionVisionList<ProductionVisionCamera>(cameras), stations: normalizeProductionVisionList<ProductionVisionStation>(stations), zones: normalizeProductionVisionList<ProductionVisionZone>(zones) }; },
  saveCamera: (input: ProductionVisionCameraInput, cameraId?: string) => apiRequest<ProductionVisionCamera>(cameraId ? "PUT" : "POST", cameraId ? `/production-vision/cameras/${cameraId}` : "/production-vision/cameras", input),
  saveZone: (input: ProductionVisionZoneInput, zoneId?: string) => apiRequest<ProductionVisionZone>(zoneId ? "PUT" : "POST", zoneId ? `/production-vision/zones/${zoneId}` : "/production-vision/zones", input),
  deleteZone: (zoneId: string) => apiRequest<{ deleted: boolean }>("DELETE", `/production-vision/zones/${zoneId}`),
  saveStation: (input: ProductionVisionStationInput, stationId?: string) => apiRequest<ProductionVisionStation>(stationId ? "PUT" : "POST", stationId ? `/production-vision/stations/${stationId}` : "/production-vision/stations", input),
  deleteStation: (stationId: string) => apiRequest<{ deleted: boolean }>("DELETE", `/production-vision/stations/${stationId}`),
};
