import { describe, expect, it } from "vitest";
import {
  buildPlatformTenantListQuery,
  isPlatformInvoicePaymentAvailable,
  normalizePlatformHostnameInput,
  normalizePlatformReason,
  PLATFORM_TENANT_LIST_FILTER_KEYS,
} from "./platformMaster";
import { ApiRequestError, isApiRequestErrorStatus } from "./api";

describe("platform master presentation helpers", () => {
  it("distinguishes a denied Master request from transient API failures", () => {
    expect(isApiRequestErrorStatus(new ApiRequestError("Forbidden", 403), 403)).toBe(true);
    expect(isApiRequestErrorStatus(new ApiRequestError("Unavailable", 503), 403)).toBe(false);
    expect(isApiRequestErrorStatus(new Error("network"), 403)).toBe(false);
  });

  it("normalizes hostnames without accepting URL paths", () => {
    expect(normalizePlatformHostnameInput(" HTTPS://Loja.Exemplo.COM.BR./checkout ")).toBe("loja.exemplo.com.br");
  });

  it("hides manual payment actions for final invoice states", () => {
    expect(isPlatformInvoicePaymentAvailable("paid")).toBe(false);
    expect(isPlatformInvoicePaymentAvailable("cancelled")).toBe(false);
    expect(isPlatformInvoicePaymentAvailable("refunded")).toBe(false);
    expect(isPlatformInvoicePaymentAvailable("courtesy")).toBe(false);
    expect(isPlatformInvoicePaymentAvailable("pending")).toBe(true);
    expect(isPlatformInvoicePaymentAvailable("overdue")).toBe(true);
  });

  it("normalizes audit reasons before sending", () => {
    expect(normalizePlatformReason("  Bloqueio   solicitado pelo financeiro  ")).toBe(
      "Bloqueio solicitado pelo financeiro",
    );
  });

  it("keeps the tenant list query aligned with the functional backend filters", () => {
    expect(PLATFORM_TENANT_LIST_FILTER_KEYS).toEqual([
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
    ]);
    expect(buildPlatformTenantListQuery({
      page: 2,
      tenant_id: "tenant-123",
      email: "owner@example.com",
      plan_id: "plan-pro",
      domain: "loja.example.com",
      billing_status: "overdue",
      module: "crm",
      expiring_days: 7,
    })).toBe(
      "page=2&tenant_id=tenant-123&email=owner%40example.com&plan_id=plan-pro&domain=loja.example.com&billing_status=overdue&module=crm&expiring_days=7",
    );
  });
});
