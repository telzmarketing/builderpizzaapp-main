import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ApiStrategicCampaign } from "@/lib/api";
import StrategicCampaignLandingEditor from "./StrategicCampaignLandingEditor";

const campaign: ApiStrategicCampaign = {
  id: "campaign-1", name: "Natal", commercial_name: "Natal Gran Torino", slug: "natal", description: null, status: "draft", starts_at: null, ends_at: null, visual_config: {},
  commercial_config: { sales_mode: "immediate", allow_when_store_closed: false, require_scheduled_order: false, min_lead_minutes: 0, max_lead_days: null, allowed_payment_methods: [] },
  marketing_config: { planned_budget: null, traffic_campaign_id: null, attribution_window_days: 30 }, published_version: 1,
  offers: [{ id: "offer-1", campaign_id: "campaign-1", code: "NATAL", title: "Oferta", description: null, product_id: "product-1", kit_id: null, price_original: 50, price_promotional: 40, active: true, display_order: 0, quantity_limit: null, max_per_customer: null, sales_starts_at: null, sales_ends_at: null, show_when_sold_out: false, button_text: null, image_desktop_url: null, image_mobile_url: null, badge_text: null, highlighted: false, config: {}, archived_at: null }],
};

describe("StrategicCampaignLandingEditor", () => {
  it("exposes the complete builder and keeps published campaigns editable as drafts", () => {
    const html = renderToStaticMarkup(<StrategicCampaignLandingEditor campaign={campaign} onChanged={() => undefined} />);
    expect(html).toContain("Editor da Landing Page");
    expect(html).toContain("Desktop");
    expect(html).toContain("Tablet");
    expect(html).toContain("Mobile");
    expect(html).toContain("Publicar nova versão");
    expect(html).toContain("Você está editando o rascunho");
    expect(html).toContain('data-testid="strategic-campaign-renderer-preview"');
  });
});
