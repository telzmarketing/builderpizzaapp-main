import { describe, expect, it } from "vitest";
import {
  CUSTOMER_AI_ALLOWED_AREAS,
  CUSTOMER_AI_SCOPE_GUARDRAIL,
  ensureCustomerAiScope,
} from "./customerAiScope";

describe("customer AI scope", () => {
  it("keeps the customer-facing areas limited to the approved list", () => {
    expect(CUSTOMER_AI_ALLOWED_AREAS).toEqual([
      "Catálogo",
      "Promoções",
      "FAQs",
      "Frete",
      "Pedidos",
    ]);
  });

  it("adds the guardrail without duplicating it", () => {
    const saved = ensureCustomerAiScope("Não invente preços.");

    expect(saved).toContain("Não invente preços.");
    expect(saved).toContain(CUSTOMER_AI_SCOPE_GUARDRAIL);
    expect(ensureCustomerAiScope(saved)).toBe(saved);
  });

  it("can persist the guardrail when the field starts empty", () => {
    expect(ensureCustomerAiScope("")).toBe(CUSTOMER_AI_SCOPE_GUARDRAIL);
  });
});
