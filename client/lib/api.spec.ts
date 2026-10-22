import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildApiBases, companyDomainsApi, inventoryFoundationApi, inventoryReceiptApi, kdsApi, platformDomainsApi, platformTenantsApi, preparationApi, productRecipesApi } from "./api";

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

describe("multi-operator KDS contracts", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
    vi.stubGlobal("window", { location: { pathname: "/painel/cozinha", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("sends versioned presence changes with idempotency and never retries", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: { operator_id: "op-1", state: "available", version: 3 } }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await kdsApi.setPresence({ state: "available", expected_version: 2 }, "presence-2");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/kds\/kitchen\/presence$/);
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("presence-2");
    expect(JSON.parse(String(init.body))).toEqual({ state: "available", expected_version: 2 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps task commands on the official API client with encoded ids", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: { id: "task-1", state: "assembling" } }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await kdsApi.commandTask("task/1", "start", { expected_version: 4 }, "task-start-4");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/kds\/kitchen\/tasks\/task%2F1\/start$/);
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("task-start-4");
  });
});

describe("operational recipe contracts", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
    vi.stubGlobal("window", { location: { pathname: "/painel/products", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("publishes entered Decimal quantities without frontend conversion and encodes IDs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "version2" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await productRecipesApi.create("pizza/id", { expected_version: 1, reference_fraction: "0.5", items: [{ inventory_item_id: "cheese", entered_quantity: "150.000001", entered_unit_id: "g", unit_id: "kg" }] } as never, "publish-1");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/gestao\/inventory\/v1\/products\/pizza%2Fid\/recipes$/);
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("publish-1");
    const row = JSON.parse(String(init.body)).items[0];
    expect(row.entered_quantity).toBe("150.000001");
    expect(row).not.toHaveProperty("quantity");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("keeps the server history/version response and surfaces concurrency conflicts without retry", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ items: [], latest_version: 7, next_cursor: null }), { headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { message: "Versao desatualizada" } }), { status: 409, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    expect((await productRecipesApi.list("pizza")).latest_version).toBe(7);
    await expect(productRecipesApi.archive("pizza", "v7", 7, "archive-7")).rejects.toMatchObject({ status: 409 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it("does not send credentials or make a request for arbitrary image URLs", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    await expect(productRecipesApi.imageBlob("https://example.com/image.png")).rejects.toThrow("invalida");
    await expect(productRecipesApi.imageBlob("/api/gestao/inventory/recipe-images/../secret")).rejects.toThrow("invalida");
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("loads private image content as a blob and never caches it", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("image content", { headers: { "Content-Type": "image/png" } }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await productRecipesApi.imageBlob("/api/gestao/inventory/recipe-images/abc123")).toBeInstanceOf(Blob);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/gestao\/inventory\/recipe-images\/abc123$/);
    expect(init.cache).toBe("no-store");
  });
  it("sends preview customizations to the backend without calculating quantities", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ complete: false, missing: ["product:B"] }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const body = { product_id: "A", quantity: 2, flavors: [{ product_id: "A" }, { product_id: "B" }], customizations: [{ action: "remove", inventory_item_id: "onion", scope_product_id: "B" }] };
    expect((await productRecipesApi.preview(body)).complete).toBe(false);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/gestao\/inventory\/v1\/composition\/preview$/);
    expect(JSON.parse(String(init.body))).toEqual(body);
  });
});

describe("supplier receipt contracts", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
    vi.stubGlobal("window", { location: { pathname: "/painel/gestao/inventory", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("uploads XML once with an idempotency key and does not retry the mutation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "doc-1", status: "pending_review" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["<nfeProc />"], "entrada.xml", { type: "application/xml" });
    await inventoryReceiptApi.uploadXml(file, null, "document-key");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("document-key");
    expect(init.body).toBeInstanceOf(FormData);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sends versioned payable reconciliation without a payment command", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ document_id: "doc-1", status: "linked", transaction_ids: ["trx-1"], obligation_total: "400.00", paid_total: "0.00" }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await inventoryReceiptApi.reconcilePayables("doc/1", { expected_version: 3, installments: [{ number: 1, due_date: "2026-11-01", amount: "400.00" }] }, "payable-key");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/gestao\/inventory\/v1\/documents\/doc%2F1\/payables\/reconcile$/);
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("payable-key");
    expect(JSON.parse(String(init.body))).toEqual({ expected_version: 3, installments: [{ number: 1, due_date: "2026-11-01", amount: "400.00" }] });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("preparation contracts", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
    vi.stubGlobal("window", { location: { pathname: "/painel/gestao/estoque", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("sends version and idempotency for physical preparation commands", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: { id: "prep-1", version: 4 } }), { headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await preparationApi.report("prep/1", { expected_version: 3, produced_quantity: "10.000000", approved_quantity: "10.000000", discarded_quantity: "0.000000", input_allocations: [], losses: [], reason: null }, "report-1");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/preparation\/orders\/prep%2F1\/reports$/);
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("report-1");
    expect(JSON.parse(String(init.body)).expected_version).toBe(3);
  });

  it("does not retry a planning mutation after a conflict", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: "Versao desatualizada" } }), { status: 409, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(preparationApi.manage("prep-1", "approve", { expected_version: 2 }, "approve-1")).rejects.toMatchObject({ status: 409 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
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


describe("inventory foundation Decimal and command contracts", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
    vi.stubGlobal("window", { location: { pathname: "/painel/gestao/estoque", replace: vi.fn() } });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it("loads all lookup pages without hiding the next cursor", async () => {
    const json = (body: unknown) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
    const fetchMock = vi.fn().mockResolvedValueOnce(json({ items: [{ id: "first" }], next_cursor: "cursor/first" }))
      .mockResolvedValueOnce(json({ items: [{ id: "second" }], next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await inventoryFoundationApi.units();
    expect(result.items.map((row) => row.id)).toEqual(["first", "second"]);
    expect(fetchMock.mock.calls[1][0]).toMatch(/units\?cursor=cursor%2Ffirst$/);
  });
  it("preserves Decimal strings and the supplied permanent command key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "operation" }), {
      status: 201, headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    await inventoryFoundationApi.command("operations", { quantity: "0.100001", expected_version: 0 }, "physical-event");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/gestao\/inventory\/v1\/operations$/);
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("physical-event");
    expect(JSON.parse(String(init.body)).quantity).toBe("0.100001");
  });
  it("does not retry a failed physical mutation against another API base", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: "Indisponivel" } }), {
      status: 503, headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(inventoryFoundationApi.command("operations", { expected_version: 0 }, "same-event")).rejects.toThrow("Indisponivel");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
