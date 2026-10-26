import type { DeliveryRecord } from "./api";
import { operationalPaymentLines } from "./operationalPayment";

/** Adapt the driver's existing nested payment projection without assuming a gateway. */
export function driverPaymentLines(delivery: DeliveryRecord): string[] {
  const order = delivery.order;
  const payment = order?.payment;
  return operationalPaymentLines({
    payment_status: payment?.status ?? order?.payment_status,
    payment_method: payment?.method,
    pay_on_delivery: payment?.pay_on_delivery ?? order?.pay_on_delivery,
    delivery_payment_method: payment?.delivery_payment_method ?? order?.delivery_payment_method,
    cash_needs_change: payment?.cash_needs_change ?? order?.cash_needs_change,
    cash_change_for: payment?.cash_change_for ?? order?.cash_change_for,
  });
}

export function driverAvailabilityLabel(status: string): string {
  return ({ available: "Disponível", busy: "Com entrega atribuída", reserved: "Reservado", returning: "Retornando", unavailable: "Indisponível", offline: "Offline" } as Record<string, string>)[status] ?? status;
}
