const ORDER_ARCHIVED_EVENT = "telz:order-archived";
const ORDER_ARCHIVED_STORAGE_KEY = "telz:last-order-archived";

type OrderArchivedDetail = { orderId: string; at: number };

function parseDetail(value: string | null): OrderArchivedDetail | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as Partial<OrderArchivedDetail>;
    return typeof parsed.orderId === "string" && typeof parsed.at === "number"
      ? { orderId: parsed.orderId, at: parsed.at }
      : null;
  } catch {
    return null;
  }
}
/** Notify open operational/reporting surfaces after an order is archived. */
export function notifyOrderArchived(orderId: string) {
  const detail: OrderArchivedDetail = { orderId, at: Date.now() };
  try {
    localStorage.setItem(ORDER_ARCHIVED_STORAGE_KEY, JSON.stringify(detail));
  } catch {
    // The in-document event below still refreshes the current tab.
  }
  window.dispatchEvent(new CustomEvent<OrderArchivedDetail>(ORDER_ARCHIVED_EVENT, { detail }));
}

/** Subscribe to archive notifications from this tab and other open tabs. */
export function onOrderArchived(callback: (detail: OrderArchivedDetail) => void) {
  const onEvent = (event: Event) => {
    const detail = (event as CustomEvent<OrderArchivedDetail>).detail;
    if (detail?.orderId) callback(detail);
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key !== ORDER_ARCHIVED_STORAGE_KEY) return;
    const detail = parseDetail(event.newValue);
    if (detail) callback(detail);
  };
  window.addEventListener(ORDER_ARCHIVED_EVENT, onEvent);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(ORDER_ARCHIVED_EVENT, onEvent);
    window.removeEventListener("storage", onStorage);
  };
}

