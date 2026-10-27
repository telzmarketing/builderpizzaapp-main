import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { biApi, type ApiBIMobileFilters } from "./api";

const filters: ApiBIMobileFilters = {
  date: "2026-10-27",
  period: "90d",
  compare: "previous_period",
  partial: false,
  monthly: "12m",
  view: "general",
  grouping: "week",
};

describe("BI mobile API contracts", () => {
  beforeEach(() => {
    const storage = {
      getItem: (key: string) =>
        key === "admin_token" ? "bi-admin-token" : null,
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal("sessionStorage", { ...storage, getItem: () => null });
    vi.stubGlobal("window", {
      location: { pathname: "/painel/bi/mobile", replace: vi.fn() },
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends independent period, monthly and grouping filters through the authenticated API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { generated_at: "now" } }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await biApi.mobileAnalytics(filters);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/bi/mobile/analytics?");
    const query = new URL(url, "http://test.local").searchParams;
    for (const [key, value] of Object.entries(filters))
      expect(query.get(key)).toBe(String(value));
    expect(new Headers(init.headers).get("Authorization")).toBe(
      "Bearer bi-admin-token",
    );
  });

  it("preserves the selected period for analysis and never retries an uncertain mutation", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("connection lost"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(biApi.mobileAnalyze(filters)).rejects.toThrow(
      "connection lost",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/bi\/mobile\/analyze$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(filters);
  });
});
