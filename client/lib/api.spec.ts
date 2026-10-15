import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildApiBases, companyDomainsApi, platformDomainsApi, platformTenantsApi } from "./api";

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

describe("buildApiBases", () => {
  it("prioritizes the proxied API prefix in production", () => {
    expect(buildApiBases("", true, false)).toEqual(["/api", ""]);
  });

  it("prioritizes the FastAPI prefix in local development", () => {
    expect(buildApiBases("http://localhost:8000", false, true)).toEqual([
      "http://localhost:8000/api",
      "http://localhost:8000",
      "/api",
      "",
    ]);
  });

  it("does not duplicate an explicitly configured API prefix", () => {
    expect(buildApiBases("https://erp.example.com/api/", true, false)).toEqual([
      "https://erp.example.com/api",
      "",
    ]);
  });

  it("ignores a localhost API base in production", () => {
    expect(buildApiBases("http://localhost:8000", true, false)).toEqual(["/api", ""]);
  });
});

describe("platform tenant mutations", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
    vi.stubGlobal("window", {
      location: { pathname: "/painel/empresas", replace: vi.fn() },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("posts company provisioning directly to the canonical API route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: true,
      data: { tenant: { id: "tenant-1" } },
    }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await platformTenantsApi.create({} as never);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/admin\/platform\/tenants$/);
    expect(init.method).toBe("POST");
  });

  it("preserves the backend detail from a final 404 without retrying the post", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "Plano informado nao existe ou esta inativo.",
    }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    const request = platformTenantsApi.create({} as never);

    await expect(request).rejects.toMatchObject({
      status: 404,
      message: "Plano informado nao existe ou esta inativo.",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps certificate issuance on the canonical route with the caller's idempotency key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "DNS ainda nao aponta para a plataforma.",
    }), { status: 409, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(platformDomainsApi.requestCertificate("domain-1", {
      email: "admin@example.com", accept_terms: true,
    }, "attempt-1")).rejects.toMatchObject({ status: 409, message: "DNS ainda nao aponta para a plataforma." });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/admin\/platform\/domains\/domain-1\/certificate$/);
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("attempt-1");
    expect(JSON.parse(init.body as string)).toEqual({ email: "admin@example.com", accept_terms: true });
  });

  it("uses the company endpoint without accepting a tenant override in domain creation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: { domain: { id: "d1" }, verification: {} } }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await companyDomainsApi.create({ hostname: "loja.example.com", kind: "custom", tenant_id: "other-tenant" } as never);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/admin\/company\/domains$/);
    expect(JSON.parse(init.body as string)).toEqual({ hostname: "loja.example.com", kind: "custom" });
    expect(new Headers(init.headers).has("X-Tenant-Id")).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("preserves company certificate permission errors and does not retry the mutation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Sem permissao para configurar dominios." }), { status: 403 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(companyDomainsApi.requestCertificate("other/domain", { email: "admin@example.com", accept_terms: true, tenant_id: "other-tenant" } as never, "company-attempt")).rejects.toMatchObject({ status: 403 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/admin\/company\/domains\/other%2Fdomain\/certificate$/);
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("company-attempt");
    expect(JSON.parse(init.body as string)).toEqual({ email: "admin@example.com", accept_terms: true });
    expect(new Headers(init.headers).has("X-Tenant-Id")).toBe(false);
  });
});
