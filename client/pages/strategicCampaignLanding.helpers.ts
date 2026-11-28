import type { StoreOperationStatus } from "@/lib/api";

export type StrategicSalesMode = "immediate" | "preorder" | "hybrid";

export function immediateChoiceEnabled(
  mode: StrategicSalesMode,
  storeStatus: Pick<StoreOperationStatus, "is_open"> | null,
  loading: boolean,
) {
  return mode !== "preorder" && !loading && storeStatus?.is_open === true;
}

export function shouldKeepAvailabilityStep(
  mode: StrategicSalesMode,
  storeIsOpen: boolean,
  hasAvailableSlot: boolean,
) {
  return mode === "hybrid" || mode === "preorder" || hasAvailableSlot || !storeIsOpen;
}
