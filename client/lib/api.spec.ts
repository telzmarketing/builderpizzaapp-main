import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildApiBases, platformTenantsApi } from "./api";

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
});
