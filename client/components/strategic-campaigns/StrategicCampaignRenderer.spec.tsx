import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ApiStrategicCampaign } from "@/lib/api";
import StrategicCampaignRenderer from "./StrategicCampaignRenderer";
import { createStrategicCampaignVisualConfig } from "./strategicCampaignVisual";

const campaign: ApiStrategicCampaign = {
  id: "campaign-1", name: "Festival", commercial_name: "Festival Gran Torino", slug: "festival", description: "Condições especiais", status: "active", starts_at: null, ends_at: "2099-12-31T23:59:59Z",
  visual_config: {}, commercial_config: { sales_mode: "immediate", allow_when_store_closed: false, require_scheduled_order: false, min_lead_minutes: 0, max_lead_days: null, allowed_payment_methods: [] },
  marketing_config: { planned_budget: null, traffic_campaign_id: null, attribution_window_days: 30 }, published_version: 2,
  offers: [{ id: "offer-1", campaign_id: "campaign-1", code: "PIZZA", title: "Pizza especial", description: "Monte do seu jeito", product_id: "product-1", kit_id: null, reference_type: "product", components: [], pricing_strategy: "catalog", discount_percent: null, discount_amount: null, fixed_promotional_price: null, composition_revision: 1, price_original: 79.9, price_promotional: 59.9, active: true, display_order: 0, quantity_limit: null, max_per_customer: null, sales_starts_at: null, sales_ends_at: null, show_when_sold_out: false, button_text: "Configurar", image_desktop_url: "/desktop.webp", image_mobile_url: "/mobile.webp", badge_text: "Destaque", highlighted: true, config: {}, archived_at: null }],
};

describe("StrategicCampaignRenderer", () => {
  it("renders the same visual document in preview with responsive media and canonical CTA", () => {
    const config = createStrategicCampaignVisualConfig({ ...campaign, visual_config: { hero: { imageDesktopUrl: "/hero-desktop.webp", imageMobileUrl: "/hero-mobile.webp" }, information: { enabled: true, title: "Regras", body: "Consulte as condições" } } });
    const html = renderToStaticMarkup(<StrategicCampaignRenderer campaign={campaign} config={config} mode="preview" viewport="mobile" />);
    expect(html).toContain('data-testid="strategic-campaign-renderer-preview"');
    expect(html).toContain("/hero-mobile.webp");
    expect(html).toContain("Pizza especial");
    expect(html).toContain("Configurar");
    expect(html).toContain("Regras");
  });

  it("does not render archived offers", () => {
    const archived = { ...campaign, offers: [{ ...campaign.offers[0], archived_at: "2026-11-26T00:00:00Z" }] };
    const html = renderToStaticMarkup(<StrategicCampaignRenderer campaign={archived} mode="public" />);
    expect(html).not.toContain("Pizza especial");
    expect(html).toContain("Adicione e ative ofertas");
  });
});
