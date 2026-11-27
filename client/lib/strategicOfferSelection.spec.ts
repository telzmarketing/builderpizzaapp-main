import { describe, expect, it } from "vitest";
import type { ApiProduct } from "./api";
import {
  buildStrategicOfferSelection,
  campaignLabel,
  normalizeStrategicOfferConfiguration,
  strategicCampaignIdFromTab,
  strategicCampaignTab,
  type ConfiguredStrategicStep,
} from "./strategicOfferSelection";

const product = { id: "pizza-1", name: "Pizza Tradicional", price: 50 } as ApiProduct;

describe("strategic offer sales selection", () => {
  it("keeps campaign tabs stable and uses the commercial label", () => {
    expect(strategicCampaignTab("campaign-1")).toBe("strategic:campaign-1");
    expect(strategicCampaignIdFromTab("strategic:campaign-1")).toBe("campaign-1");
    expect(campaignLabel({ id: "campaign-1", name: "Interno", commercial_name: "Black Friday", slug: "black", published_version: 2, offers_available: 1 })).toBe("Black Friday");
  });

  it("normalizes and orders configuration steps from the published contract", () => {
    const configuration = normalizeStrategicOfferConfiguration({
      offer_id: "offer-1",
      campaign_id: "campaign-1",
      campaign_version: 4,
      composition_revision: 2,
      reference_type: "mixed_subcategories",
      pricing_strategy: "fixed_price",
      price_range: { minimum: 80, maximum: 120, fixed_promotional: 89.9 },
      steps: [
        { key: "special", position: 2, subcategory_id: "special", subcategory_name: "Especiais", eligible_products: [product] },
        { key: "traditional", position: 1, subcategory_id: "traditional", subcategory_name: "Tradicionais", eligible_products: [product] },
      ],
    });
    expect(configuration.steps.map((step) => step.key)).toEqual(["traditional", "special"]);
    expect(configuration.steps[0].title).toBe("Tradicionais");
    expect(configuration.reference_type).toBe("mixed_subcategories");
  });

  it("sends the exact backend group payload and keeps display metadata only on lines", () => {
    const configuration = normalizeStrategicOfferConfiguration({
      offer_id: "offer-1",
      campaign_id: "campaign-1",
      campaign_version: 4,
      composition_revision: 2,
      reference_type: "subcategory",
      pricing_strategy: "percentage",
      price_range: { minimum: 50, maximum: 50, fixed_promotional: null },
      steps: [{ key: "pizza:1", position: 1, subcategory_id: "traditional", subcategory_name: "Tradicionais", eligible_products: [product] }],
    });
    configuration.title = "Duas pizzas";
    const configured: ConfiguredStrategicStep[] = [{
      step: configuration.steps[0],
      args: [] as never,
      line: {
        id: "line-1",
        name: product.name,
        item: {
          product_id: product.id,
          quantity: 1,
          selected_size: "Grande",
          selected_size_id: "large",
          flavor_division: 1,
          flavors: [{ product_id: product.id, name: product.name, price: 50, icon: "🍕" }],
          final_price: 50,
          add_ons: [],
          option_selections: [],
        },
      },
    }];
    const result = buildStrategicOfferSelection(configuration, configured, "instance-1");
    expect(result.selection).toEqual({
      offer_id: "offer-1",
      campaign_version: 4,
      composition_revision: 2,
      quantity: 1,
      selections: [{ step_key: "pizza:1", item: configured[0].line.item }],
    });
    expect(result.selection).not.toHaveProperty("instance_id");
    expect(result.lines[0].strategic?.group).toMatchObject({
      instanceId: "instance-1",
      campaignVersion: 4,
      compositionRevision: 2,
      referenceType: "subcategory",
      sourceSubcategoryId: "traditional",
      stepKey: "pizza:1",
    });
  });
});
