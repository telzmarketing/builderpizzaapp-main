import { describe, expect, it } from "vitest";
import { DEFAULT_PARTNER_IDENTIFICATION, isPartnerOrigin, normalizePartnerIdentification, partnerOriginLabel } from "./partnerIdentification";

describe("partner identification", () => {
  it("keeps the four supported origins and applies configured names", () => {
    const partners = normalizePartnerIdentification({ partners: [{ order_origin: "ifood", display_name: "iFood da loja", logo_url: "/uploads/ifood.png", enabled: true }] });
    expect(partners).toHaveLength(DEFAULT_PARTNER_IDENTIFICATION.length);
    expect(partnerOriginLabel("ifood", partners)).toBe("iFood da loja");
    expect(partners.find((item) => item.order_origin === "keeta")?.display_name).toBe("KEETA");
  });

  it("requires an external number only for partner origins", () => {
    expect(isPartnerOrigin("own")).toBe(false);
    expect(isPartnerOrigin("partner_99")).toBe(true);
    expect(isPartnerOrigin("ifood")).toBe(true);
    expect(isPartnerOrigin("keeta")).toBe(true);
  });
});
