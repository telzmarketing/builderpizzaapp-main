export const PIZZA_SIZE_LABELS = ["Pizza Broto", "Pizza Grande"];

const PIZZA_SIZE_DETAILS: Record<string, { label: string; description: string }> = {
  brotinho: { label: "Pizza Broto", description: "25cm - 4 pedaços" },
  "pizza broto": { label: "Pizza Broto", description: "25cm - 4 pedaços" },
  "pizza grande": { label: "Pizza Grande", description: "35cm - 8 pedaços" },
};

export function isAllowedPizzaSize(label: string) {
  return Boolean(PIZZA_SIZE_DETAILS[label.trim().toLowerCase()]);
}

export function pizzaSizeLabel(label: string) {
  return PIZZA_SIZE_DETAILS[label.trim().toLowerCase()]?.label ?? label;
}

export function pizzaSizeDescription(label: string, fallback?: string | null) {
  return PIZZA_SIZE_DETAILS[label.trim().toLowerCase()]?.description ?? fallback ?? "";
}

export function isPizzaBroto(label: string) {
  return pizzaSizeLabel(label) === "Pizza Broto";
}
