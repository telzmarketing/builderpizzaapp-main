import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import StrategicOfferConfigurator from "./StrategicOfferConfigurator";
import { normalizeStrategicOfferConfiguration } from "@/lib/strategicOfferSelection";

describe("StrategicOfferConfigurator", () => {
  it("starts the published composition in sequential order", () => {
    const configuration = normalizeStrategicOfferConfiguration({
      offer_id: "offer",
      campaign_id: "campaign",
      campaign_version: 1,
      composition_revision: 1,
      reference_type: "mixed_subcategories",
      pricing_strategy: "fixed_price",
      price_range: { minimum: 80, maximum: 100, fixed_promotional: 89.9 },
      steps: [
        { key: "traditional:1", position: 1, subcategory_id: "traditional", subcategory_name: "Tradicionais", eligible_products: [{ id: "pizza", name: "Pizza", price: 50, icon: "🍕" }] },
        { key: "special:1", position: 2, subcategory_id: "special", subcategory_name: "Especiais", eligible_products: [{ id: "special", name: "Especial", price: 60, icon: "🍕" }] },
      ],
    });
    configuration.title = "Black Friday";
    const html = renderToStaticMarkup(<StrategicOfferConfigurator configuration={configuration} onCancel={() => {}} onComplete={() => {}} />);
    expect(html).toContain("Etapa 1 de 2");
    expect(html).toContain("Tradicionais");
    expect(html).toContain("Pizza");
    expect(html).toContain("Especiais");
  });
});
