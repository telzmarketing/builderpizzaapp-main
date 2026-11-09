import { describe, expect, it } from "vitest";
import type { InventoryAdjustmentBucket } from "@/lib/api";
import { adjustmentInput, adjustmentReady, selectedAdjustmentBucket, validAdjustmentQuantity } from "./InventoryStockAdjustmentDialog";

const buckets: InventoryAdjustmentBucket[] = [
  { location_id: "cold", location_name: "Câmara", lot_id: "lot-a", lot_code: "A", physical: "12.500000", reserved: "2", available: "10.5", unit_symbol: "KG" },
  { location_id: "cold", location_name: "Câmara", lot_id: "lot-b", lot_code: "B", physical: "8.000000", reserved: "1", available: "7", unit_symbol: "KG" },
];

describe("ajuste de estoque", () => {
  it("exige seleção explícita do bucket quando há mais de um local/lote", () => {
    expect(selectedAdjustmentBucket(buckets, "")).toBeUndefined();
    expect(adjustmentReady(selectedAdjustmentBucket(buckets, ""), true, "Contagem", true)).toBe(false);
    expect(selectedAdjustmentBucket(buckets, "1")).toEqual(buckets[1]);
  });

  it("distingue saldo contado de quantidade perdida e preserva o bucket selecionado", () => {
    expect(validAdjustmentQuantity("7,125", "correction", false)).toBe(true);
    expect(validAdjustmentQuantity("0", "correction", false)).toBe(true);
    expect(validAdjustmentQuantity("0", "loss", false)).toBe(false);
    expect(validAdjustmentQuantity("1.1234567", "loss", false)).toBe(false);
    expect(validAdjustmentQuantity("2.5", "loss", true)).toBe(false);
    expect(validAdjustmentQuantity("2", "loss", true)).toBe(true);

    expect(adjustmentInput(buckets[1], "event-1", "correction", "7,125", " Inventário ", "")).toEqual({
      business_key: "event-1", kind: "correction", quantity: "7.125", expected_physical: "8.000000", location_id: "cold", lot_id: "lot-b", reason: "Inventário",
    });
    expect(adjustmentInput(buckets[0], "event-2", "loss", "2", " Quebra ", "Validade")).toMatchObject({
      business_key: "event-2", kind: "loss", quantity: "2", expected_physical: "12.500000", lot_id: "lot-a", reason: "Quebra", notes: "Validade",
    });
  });

  it("exige motivo e confirmação antes do envio", () => {
    expect(adjustmentReady(buckets[0], true, "", true)).toBe(false);
    expect(adjustmentReady(buckets[0], true, "Quebra", false)).toBe(false);
    expect(adjustmentReady(buckets[0], false, "Quebra", true)).toBe(false);
    expect(adjustmentReady(buckets[0], true, "Quebra", true)).toBe(true);
  });
});
