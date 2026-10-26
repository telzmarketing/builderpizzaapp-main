export function optionalMetric(value: number | null | undefined, percentage = false): string {
  if (value == null || !Number.isFinite(value)) return "Indispon\u00edvel";
  return percentage ? `${(value * 100).toFixed(1)}%` : value.toLocaleString("pt-BR");
}
