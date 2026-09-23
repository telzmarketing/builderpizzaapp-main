import type { KdsKitchenOrder } from "./api";

const KITCHEN_ACTIVE_STATUSES = new Set(["paid", "pago", "preparing"]);

export function activeKitchenOrders(orders: KdsKitchenOrder[]): KdsKitchenOrder[] {
  return orders.filter((order) =>
    KITCHEN_ACTIVE_STATUSES.has(order.status)
    || (order.status === "ready_for_pickup" && order.fulfillment_type === "pickup"),
  );
}

export function clearAssignedDriverSelections(
  selections: Record<string, string>,
  assignedDriverId: string,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(selections).filter(([, driverId]) => driverId !== assignedDriverId),
  );
}
