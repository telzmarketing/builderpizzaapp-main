import { describe, expect, it } from "vitest";
import { formatPrintOrderMoney, PRINT_ORDER_FINANCIAL_FIELDS, PRINT_ORDER_REVIEW_FIELDS } from "./PrintOrder";

describe("Print Pedido review presentation", () => {
  it("exposes correctly labeled address and payment fields", () => {
    expect(PRINT_ORDER_REVIEW_FIELDS).toEqual(expect.arrayContaining([
      { name: "delivery_street", label: "Endereço" },
      { name: "delivery_city", label: "Cidade" },
      { name: "delivery_complement", label: "Complemento" },
      { name: "payment_method", label: "Forma de pagamento" },
    ]));
  });

  it("exposes the financial fields used by the reconciliation payload", () => {
    expect(PRINT_ORDER_FINANCIAL_FIELDS.map((field) => field.name)).toEqual([
      "subtotal", "delivery_fee", "service_fee", "store_discount",
      "platform_discount", "total_paid", "printed_total",
    ]);
  });

  it("formats reconciliation amounts without hiding zero or negative values", () => {
    expect(formatPrintOrderMoney("38.79")).toBe("R$ 38,79");
    expect(formatPrintOrderMoney(-24.99)).toBe("-R$ 24,99");
    expect(formatPrintOrderMoney(null)).toBe("Não informado");
  });
});
