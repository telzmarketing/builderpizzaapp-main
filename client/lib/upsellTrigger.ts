import type { ApiUpsellInput, ApiUpsell } from "./api";

export type UpsellTriggerMode = "product" | "category" | "subcategory" | "any";

export function getUpsellTriggerMode(upsell: Pick<ApiUpsell, "trigger_type" | "trigger_product_id" | "trigger_category"> & Partial<Pick<ApiUpsell, "trigger_subcategory" | "trigger_subcategory_id">>): UpsellTriggerMode {
  if (upsell.trigger_type === "subcategory" || upsell.trigger_subcategory_id || upsell.trigger_subcategory) return "subcategory";
  if (upsell.trigger_type === "category") return "category";
  if (upsell.trigger_type === "product_in_cart") return "product";
  return "any";
}

export function applyUpsellTrigger(
  input: ApiUpsellInput,
  mode: UpsellTriggerMode,
  value: string | null,
  label?: string | null,
): ApiUpsellInput {
  return {
    ...input,
    trigger_type: mode === "category" ? "category" : mode === "subcategory" ? "subcategory" : mode === "product" ? "product_in_cart" : "min_value",
    trigger_product_id: mode === "product" ? value : null,
    trigger_category: mode === "category" ? (label ?? value) : null,
    trigger_category_id: mode === "category" ? value : null,
    trigger_subcategory: mode === "subcategory" ? (label ?? value) : null,
    trigger_subcategory_id: mode === "subcategory" ? value : null,
  };
}
