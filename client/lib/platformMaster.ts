import type { ApiPlatformInvoice } from "@/lib/api";

export const PLATFORM_TENANT_LIST_FILTER_KEYS = [
  "page",
  "page_size",
  "q",
  "status",
  "sort_by",
  "sort_dir",
  "tenant_id",
  "email",
  "plan_id",
  "domain",
  "billing_status",
  "module",
  "expiring_days",
] as const;

export type PlatformTenantListFilterKey = typeof PLATFORM_TENANT_LIST_FILTER_KEYS[number];
export type PlatformTenantListFilters = Partial<Record<PlatformTenantListFilterKey, string | number>>;

const FINAL_INVOICE_STATUSES = new Set<ApiPlatformInvoice["status"]>([
  "paid",
  "cancelled",
  "refunded",
  "courtesy",
]);

export function normalizePlatformHostnameInput(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .split("/")[0]
    .replace(/\.$/, "");
}

export function isPlatformInvoicePaymentAvailable(status: ApiPlatformInvoice["status"]): boolean {
  return !FINAL_INVOICE_STATUSES.has(status);
}

export function normalizePlatformReason(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function buildPlatformTenantListQuery(params: PlatformTenantListFilters): string {
  const query = new URLSearchParams();
  PLATFORM_TENANT_LIST_FILTER_KEYS.forEach((key) => {
    const value = params[key];
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return query.toString();
}
