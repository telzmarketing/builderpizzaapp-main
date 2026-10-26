import { describe, expect, it } from "vitest";
import { operationalPaymentHtml, operationalPaymentLines } from "./operationalPayment";

describe("read-only operational payment facts", () => {
  it("never infers confirmation from delivery flag or operational status", () => {
    expect(operationalPaymentLines({ pay_on_delivery: false, payment_status: "pending", payment_method: "credit_card" }).join(" ")).toContain("Pagamento pendente");
    expect(operationalPaymentLines({ pay_on_delivery: false }).join(" ")).not.toContain("CONFIRMADO");
  });
  it("requires confirmed status and online provider for the online warning", () => {
    expect(operationalPaymentLines({ payment_status: "approved", payment_provider: "mercado_pago" })[0]).toBe("PAGO ONLINE — NÃO COBRAR");
    expect(operationalPaymentLines({ payment_status: "approved", payment_provider: "salao" })[0]).toBe("PAGAMENTO CONFIRMADO — NÃO COBRAR");
    expect(operationalPaymentLines({ payment_status: "pending", payment_provider: "mercado_pago" })[0]).toBe("Pagamento pendente");
  });
  it("shows pickup payment and backend-calculated change without changing payment", () => {
    const facts = { fulfillment_type: "pickup", payment_status: "pending", pay_on_delivery: true, delivery_payment_method: "cash", cash_needs_change: true, cash_change_for: 100, cash_change_amount: 25.01 };
    const before = JSON.stringify(facts);
    const lines = operationalPaymentLines(facts);
    expect(lines).toContain("Pagamento na retirada");
    expect(lines.find((line) => line.startsWith("TROCO:"))).toContain("25,01");
    expect(JSON.stringify(facts)).toBe(before);
  });
  it("does not offer change after payment is confirmed and escapes print values", () => {
    expect(operationalPaymentLines({ payment_status: "paid", payment_method: "cash", cash_needs_change: true, cash_change_for: 100, cash_change_amount: 25 }).some((line) => line.startsWith("TROCO:"))).toBe(false);
    expect(operationalPaymentHtml({ payment_provider: "<script>" })).toContain("&lt;script&gt;");
  });
});
