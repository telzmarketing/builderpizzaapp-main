import { describe, expect, it } from "vitest";
import { orderDisplayCode } from "./orderIdentity";

describe("public order identity", () => {
  it("prefers the persisted code over the internal order ID", () => {
    expect(orderDisplayCode({ id: "order-d5-legacy-id", order_code: "K5M4" })).toBe("K5M4");
  });

  it.each([null, undefined, "", "   "])("uses the same legacy fallback for code %s", (order_code) => {
    expect(orderDisplayCode({ id: "abc123de-1234-5678", order_code })).toBe("ABC123DE");
  });

  it("keeps leading zeroes and formats codes consistently", () => {
    expect(orderDisplayCode({ id: "internal-id", order_code: " 00k5m4 " })).toBe("00K5M4");
  });
});
