export type QuantityValue = number | string | null | undefined;

/** Formats operational quantities for display without changing calculation values. */
export function formatQuantity(value: QuantityValue, fallback = "-") {
  if (value === null || value === undefined || String(value).trim() === "") return fallback;
  const numeric = Number(String(value).trim().replace(",", "."));
  return Number.isFinite(numeric)
    ? numeric.toLocaleString("pt-BR", { useGrouping: false, maximumFractionDigits: 6 })
    : fallback;
}
