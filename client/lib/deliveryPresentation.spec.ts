import { describe, expect, it } from "vitest";
import type { DeliveryRecord } from "./api";
import { deliveryOrderCode, driverAvailabilityLabel, driverPaymentLines } from "./deliveryPresentation";

const delivery = { id: "d1", order_id: "o1", status: "assigned", estimated_minutes: 40, created_at: "2026-10-26", updated_at: "2026-10-26" } satisfies DeliveryRecord;
describe("driver operational presentation", () => {
  it("shows the canonical order code in deliveries and alerts with a consistent legacy fallback", () => {
    expect(deliveryOrderCode({ order_id: "order-d5-legacy", order: { order_code: "K5M4" } })).toBe("K5M4");
    expect(deliveryOrderCode({ order_id: "order-d5-legacy", order_code: "K5M4" })).toBe("K5M4");
    expect(deliveryOrderCode({ order_id: "abc123de-legacy" })).toBe("ABC123DE");
  });
  it("keeps unknown payment explicit and never assumes online payment", () => {
    expect(driverPaymentLines(delivery)).toEqual(["Pagamento não informado — verificar antes de cobrar", "Forma: Não informada"]);
    expect(driverPaymentLines({ ...delivery, order: { id: "o1", payment: { method: "credit_card", status: "pending" } } })).toContain("Pagamento pendente");
  });
  it("does not call a confirmed payment online without provider evidence", () => {
    const lines = driverPaymentLines({ ...delivery, order: { id: "o1", payment: { status: "paid", method: "pix" } } });
    expect(lines[0]).toBe("PAGAMENTO CONFIRMADO — NÃO COBRAR");
  });
  it("shows cash handover without inventing change absent from server", () => {
    const lines = driverPaymentLines({ ...delivery, order: { id: "o1", pay_on_delivery: true, delivery_payment_method: "cash", cash_needs_change: true, cash_change_for: 100, payment_status: "pending" } });
    expect(lines).toContain("Pagamento na entrega");
    expect(lines).toContain("Troco não informado — verificar");
  });
  it("does not label assignment as physical departure", () => {
    expect(driverAvailabilityLabel("busy")).toBe("Com entrega atribuída");
    expect(driverAvailabilityLabel("new_server_state")).toBe("new_server_state");
  });
});
