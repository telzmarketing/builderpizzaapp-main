import { isAssetUrl, resolveAssetUrl } from "./api";

/** Same tenant content used by storefront, configuration and operational receipts. */
export function storeBranding(content: { brand?: unknown; media?: unknown }) {
  const brand = (content.brand && typeof content.brand === "object" ? content.brand : {}) as Record<string, unknown>;
  const media = (content.media && typeof content.media === "object" ? content.media : {}) as Record<string, unknown>;
  const raw = [brand.logo, brand.logoUrl, media.logoUrl].find((value) => typeof value === "string" && value.trim() && isAssetUrl(value.trim()));
  return {
    name: typeof brand.name === "string" && brand.name.trim() ? brand.name.trim() : "Sua Loja",
    tagline: typeof brand.tagline === "string" ? brand.tagline.trim() : "",
    logo: typeof raw === "string" ? resolveAssetUrl(raw.trim()) : "",
  };
}
