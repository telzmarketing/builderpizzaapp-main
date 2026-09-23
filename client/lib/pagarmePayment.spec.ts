import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { paymentsApi } from "./api";

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

describe("Pagar.me browser payment boundary", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("tokenizes sensitive card data directly at Pagar.me with only the public key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: "token_browser_only",
      type: "card",
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    const token = await paymentsApi.tokenizePagarmeCard("pk_test/value", {
      number: "4111111111111111",
      holder_name: "CLIENTE TESTE",
      exp_month: "12",
      exp_year: "2030",
      cvv: "123",
    });

    expect(token.id).toBe("token_browser_only");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.pagar.me/core/v5/tokens?appId=pk_test%2Fvalue");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(init.body).toContain("4111111111111111");
    expect(JSON.stringify(init.headers)).not.toContain("Authorization");
  });

  it("sends only the temporary token to the application backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: "payment-1",
      status: "pending",
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await paymentsApi.createPagarmeCreditCard("order-1", "token_safe", 2);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(body).toEqual({
      order_id: "order-1",
      payment_method: "credit_card",
      token: "token_safe",
      installments: 2,
    });
    expect(body).not.toHaveProperty("number");
    expect(body).not.toHaveProperty("cvv");
    expect(body).not.toHaveProperty("card");
  });
});
