import { describe, expect, it } from "vitest";
import type { ApiProduct, ApiPromotionalKit, ApiStrategicOffer } from "@/lib/api";
import {
  buildStrategicOfferConfig,
  buildStrategicOfferCommercialContract,
  calculateStrategicOfferPriceRange,
  getStrategicOfferComponents,
  getStrategicOfferReferenceType,
} from "./StrategicCampaignOffersTab";

function offer(overrides: Partial<ApiStrategicOffer> = {}): ApiStrategicOffer {
  return {
    id: "offer-1",
    campaign_id: "campaign-1",
    code: "BLACK-001",
    title: "Oferta Black Friday",
    description: null,
    product_id: "product-1",
    kit_id: null,
    reference_type: "product",
    components: [],
    pricing_strategy: "catalog",
    discount_percent: null,
    discount_amount: null,
    fixed_promotional_price: null,
    composition_revision: 1,
    price_original: 100,
    price_promotional: 80,
    active: true,
    display_order: 0,
    quantity_limit: null,
    max_per_customer: null,
    sales_starts_at: null,
    sales_ends_at: null,
    show_when_sold_out: true,
    button_text: null,
    image_desktop_url: null,
    image_mobile_url: null,
    badge_text: null,
    highlighted: false,
    config: {},
    archived_at: null,
    ...overrides,
  };
}

const products = [
  { id: "traditional-1", subcategory_id: "traditional", price: 30, current_price: 28 },
  { id: "traditional-2", subcategory_id: "traditional", price: 45, current_price: 45 },
  { id: "special-1", subcategory_id: "special", price: 60, current_price: 55 },
  { id: "special-2", subcategory_id: "special", price: 75, current_price: 75 },
] as ApiProduct[];

describe("strategic offer admin commercial contract", () => {
  it("prioritizes C11 top-level reference fields and preserves component order", () => {
    const current = offer({
      reference_type: "mixed_subcategories",
      components: [
        { subcategory_id: "traditional", quantity: 2 },
        { subcategory_id: "special", quantity: 1 },
      ],
      config: { reference_type: "product", components: [{ subcategory_id: "legacy", quantity: 9 }] },
    });

    expect(getStrategicOfferReferenceType(current)).toBe("mixed_subcategories");
    expect(getStrategicOfferComponents(current).map((component) => component.subcategory_id)).toEqual(["traditional", "special"]);
  });

  it("falls back to legacy config and product/kit references", () => {
    const configured = offer({
      product_id: null,
      reference_type: undefined,
      components: undefined,
      config: {
        reference_type: "subcategory",
        components: [{ subcategory_id: "traditional", quantity: 2 }],
      },
    });
    expect(getStrategicOfferReferenceType(configured)).toBe("subcategory");
    expect(getStrategicOfferComponents(configured)).toMatchObject([{ subcategory_id: "traditional", quantity: 2 }]);

    expect(getStrategicOfferReferenceType(offer({ product_id: null, kit_id: "kit-1", reference_type: undefined }))).toBe("kit");
  });

  it("serializes mixed subcategories and percentage at top-level and in legacy config", () => {
    const contract = buildStrategicOfferCommercialContract({
      sourceType: "mixed_subcategories" as const,
      components: [
        { subcategoryId: "traditional", quantity: "2" },
        { subcategoryId: "special", quantity: "1" },
      ],
      pricingStrategy: "percentage",
      pricingValue: "15",
    });

    expect(contract).toMatchObject({
      reference_type: "mixed_subcategories",
      pricing_strategy: "percentage",
      discount_percent: 15,
      discount_amount: null,
      fixed_promotional_price: null,
      components: [
        { subcategory_id: "traditional", quantity: 1 },
        { subcategory_id: "special", quantity: 1 },
      ],
      config: {
        reference_type: "mixed_subcategories",
        pricing_strategy: "percentage",
        discount_percent: 15,
      },
    });
  });

  it("calculates the real min/max range from active subcategory products", () => {
    const range = calculateStrategicOfferPriceRange({
      sourceType: "mixed_subcategories",
      sourceId: "",
      components: [
        { subcategoryId: "traditional", quantity: "2" },
        { subcategoryId: "special", quantity: "1" },
      ],
      pricingStrategy: "fixed_discount",
      pricingValue: "10",
      priceOriginal: "",
    }, products, [] as ApiPromotionalKit[]);

    expect(range).toEqual({
      originalMinimum: 120,
      originalMaximum: 165,
      promotionalMinimum: 110,
      promotionalMaximum: 155,
    });
  });

  it("keeps product and combo contracts free of subcategory components", () => {
    const productContract = buildStrategicOfferCommercialContract({
      sourceType: "product",
      components: [{ subcategoryId: "ignored", quantity: "3" }],
      pricingStrategy: "fixed_price",
      pricingValue: "49.90",
    });
    expect(productContract.components).toEqual([]);
    expect(productContract.fixed_promotional_price).toBe(49.9);
  });

  it("serializes mixed parent-category counters and their compatibility sum", () => {
    const draft = {
      sourceType: "mixed_subcategories" as const,
      selectionQuantity: "99",
      selectionGroups: [
        { categoryId: "pizzas", subcategoryIds: ["traditional", "special"], quantity: "2" },
        { categoryId: "drinks", subcategoryIds: ["sodas"], quantity: "1" },
      ],
      components: [
        { subcategoryId: "traditional", quantity: "1" },
        { subcategoryId: "special", quantity: "1" },
        { subcategoryId: "sodas", quantity: "1" },
      ],
      pricingStrategy: "fixed_price" as const,
      pricingValue: "39.90",
    };
    const contract = buildStrategicOfferCommercialContract(draft);
    const config = buildStrategicOfferConfig(draft);

    expect(contract.selection_quantity).toBe(3);
    expect(contract.selection_groups).toEqual([
      { category_id: "pizzas", subcategory_ids: ["traditional", "special"], quantity: 2 },
      { category_id: "drinks", subcategory_ids: ["sodas"], quantity: 1 },
    ]);
    expect(config.selection_groups).toEqual(contract.selection_groups);
    expect(config.selection_quantity).toBe(3);
  });
});
