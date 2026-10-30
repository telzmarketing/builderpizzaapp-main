import type { PartnerIdentification, PartnerIdentificationResponse, PartnerOrderOrigin } from "./api";

export const PARTNER_ORIGIN_OPTIONS: Array<{ value: PartnerOrderOrigin; label: string; shortLabel: string }> = [
  { value: "own", label: "Venda própria", shortLabel: "Gran Torino" },
  { value: "partner_99", label: "99", shortLabel: "99" },
  { value: "ifood", label: "iFood", shortLabel: "iFood" },
  { value: "keeta", label: "KEETA", shortLabel: "KEETA" },
];

export const DEFAULT_PARTNER_IDENTIFICATION: PartnerIdentification[] = PARTNER_ORIGIN_OPTIONS.map(({ value, shortLabel }) => ({
  order_origin: value,
  display_name: shortLabel,
  logo_url: null,
  enabled: true,
}));

const STORAGE_KEY = "telz:partner-identification";

function storageKey() {
  return typeof window === "undefined" ? STORAGE_KEY : `${STORAGE_KEY}:${window.location.hostname}`;
}

export function normalizePartnerIdentification(value: PartnerIdentificationResponse | PartnerIdentification[] | null | undefined): PartnerIdentification[] {
  const partners = Array.isArray(value) ? value : value?.partners;
  const source = Array.isArray(partners) ? partners : [];
  return DEFAULT_PARTNER_IDENTIFICATION.map((fallback) => {
    const configured = source.find((item) => item.order_origin === fallback.order_origin);
    return {
      ...fallback,
      ...configured,
      display_name: configured?.display_name?.trim() || fallback.display_name,
      logo_url: configured?.logo_url || null,
      enabled: configured?.enabled !== false,
    };
  });
}

export function rememberPartnerIdentification(value: PartnerIdentificationResponse | PartnerIdentification[]) {
  const partners = normalizePartnerIdentification(value);
  try { localStorage.setItem(storageKey(), JSON.stringify({ partners })); } catch { /* cache is optional */ }
  return partners;
}

export function readPartnerIdentificationCache(): PartnerIdentification[] {
  try {
    const raw = JSON.parse(localStorage.getItem(storageKey()) || "null") as PartnerIdentificationResponse | null;
    return normalizePartnerIdentification(raw);
  } catch {
    return DEFAULT_PARTNER_IDENTIFICATION;
  }
}

export function partnerOriginLabel(origin?: string | null, partners = readPartnerIdentificationCache()): string {
  return partners.find((item) => item.order_origin === origin)?.display_name
    || PARTNER_ORIGIN_OPTIONS.find((item) => item.value === origin)?.shortLabel
    || "Gran Torino";
}

export function partnerLogoUrl(origin?: string | null, partners = readPartnerIdentificationCache()): string | null {
  return partners.find((item) => item.order_origin === origin)?.logo_url || null;
}

export function isPartnerOrigin(origin?: string | null): origin is Exclude<PartnerOrderOrigin, "own"> {
  return origin === "partner_99" || origin === "ifood" || origin === "keeta";
}
