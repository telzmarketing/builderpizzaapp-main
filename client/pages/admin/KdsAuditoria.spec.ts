import { describe, expect, it } from "vitest";
import { filterAuditoriaOrders, normalizeAuditoriaOrigin } from "./KdsAuditoria";

const order = (id: string, origin: string) => ({ order_id: id, order_origin: origin, status: "ready_for_pickup", delivery_id: `delivery-${id}`, delivery_status: "assigned" });

describe("KDS Auditoria helpers", () => {
  it("normalizes channel aliases and filters the queue", () => {
    expect(normalizeAuditoriaOrigin("loja_própria")).toBe("own");
    expect(filterAuditoriaOrders([order("1", "ifood"), order("2", "keeta")], "1", "ifood")).toHaveLength(1);
    expect(filterAuditoriaOrders([order("1", "ifood"), order("2", "keeta")], "", "keeta")[0].order_id).toBe("2");
  });
});
