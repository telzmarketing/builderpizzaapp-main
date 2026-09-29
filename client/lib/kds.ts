import type { KdsDispatchOrder, KdsKitchenOrder, KdsOverviewOrder, KdsOverviewStage } from "./api";

const KITCHEN_ACTIVE_STATUSES = new Set(["paid", "pago", "preparing"]);

export function activeKitchenOrders(orders: KdsKitchenOrder[]): KdsKitchenOrder[] {
  return orders.filter((order) => KITCHEN_ACTIVE_STATUSES.has(order.status));
}

export function clearAssignedDriverSelections(
  selections: Record<string, string>,
  assignedDriverId: string,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(selections).filter(([, driverId]) => driverId !== assignedDriverId),
  );
}

export function replaceDispatchOrder(
  orders: KdsDispatchOrder[],
  updated: KdsDispatchOrder,
): KdsDispatchOrder[] {
  return orders.map((order) => order.id === updated.id ? updated : order);
}

export function groupKdsOverviewOrders(
  orders: KdsOverviewOrder[],
): Record<KdsOverviewStage, KdsOverviewOrder[]> {
  return orders.reduce<Record<KdsOverviewStage, KdsOverviewOrder[]>>((groups, order) => {
    groups[order.stage].push(order);
    return groups;
  }, {
    waiting_kitchen: [],
    preparing: [],
    ready_unassigned: [],
    assigned_waiting_departure: [],
    in_route: [],
  });
}
