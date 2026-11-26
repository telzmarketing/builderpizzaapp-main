import type {
  ApiStrategicCapacitySlot,
  ApiStrategicReservation,
  StrategicReservationPaymentMode,
  StrategicReservationStatus,
} from "@/lib/api";

export const reservationStatusLabels: Record<StrategicReservationStatus, string> = {
  held: "Em retenção",
  confirmed: "Confirmada",
  released: "Liberada",
  expired: "Expirada",
  cancelled: "Cancelada",
};

export const paymentModeLabels: Record<StrategicReservationPaymentMode, string> = {
  no_payment: "Sem pagamento",
  partial: "Pagamento parcial",
  full: "Pagamento integral",
};

export function availableCapacity(slot: Pick<ApiStrategicCapacitySlot, "capacity_total" | "capacity_used">) {
  return Math.max(0, slot.capacity_total - slot.capacity_used);
}

export function canConfirmReservation(reservation: Pick<ApiStrategicReservation, "status">) {
  return reservation.status === "held";
}

export function canReleaseReservation(reservation: Pick<ApiStrategicReservation, "status">) {
  return reservation.status === "held" || reservation.status === "confirmed";
}

export function makeIdempotencyKey() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `reservation-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function validateReservationAmounts(
  mode: StrategicReservationPaymentMode,
  total: number,
  paid: number,
) {
  if (!Number.isFinite(total) || !Number.isFinite(paid) || total < 0 || paid < 0) return "Informe valores válidos.";
  if (paid > total) return "O valor pago não pode superar o valor total.";
  if (mode === "no_payment" && paid !== 0) return "Reserva sem pagamento deve ter valor pago igual a zero.";
  if (mode === "partial" && !(paid > 0 && paid < total)) return "Pagamento parcial deve ser maior que zero e menor que o total.";
  if (mode === "full" && paid !== total) return "Pagamento integral deve ser igual ao valor total.";
  return null;
}
