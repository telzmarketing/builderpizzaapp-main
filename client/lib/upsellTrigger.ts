import type { ApiUpsellInput, ApiUpsell } from "./api";

export type UpsellTriggerMode = "product" | "category" | "any";

export function getUpsellTriggerMode(upsell: Pick<ApiUpsell, "trigger_type" | "trigger_product_id" | "trigger_category">): UpsellTriggerMode {
  if (upsell.trigger_type === "category") return "category";
  if (upsell.trigger_type === "product_in_cart") return "product";
  return "any";
}

export function applyUpsellTrigger(
  input: ApiUpsellInput,
  mode: UpsellTriggerMode,
  value: string | null,
): ApiUpsellInput {
  return {
    ...input,
    trigger_type: mode === "category" ? "category" : mode === "product" ? "product_in_cart" : "min_value",
    trigger_product_id: mode === "product" ? value : null,
    trigger_category: mode === "category" ? value : null,
  };
}
