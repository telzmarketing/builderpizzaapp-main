import { describe, expect, it } from "vitest";
import type { ApiStrategicCampaign } from "@/lib/api";
import { createStrategicCampaignVisualConfig, serializeStrategicCampaignVisualConfig } from "./strategicCampaignVisual";

const campaign = (visual_config: Record<string, unknown>): ApiStrategicCampaign => ({
  id: "campaign-1", name: "Black Friday", commercial_name: "Festival Gran Torino", slug: "black-friday", description: "Oferta da casa", status: "draft", starts_at: null, ends_at: null,
  visual_config, commercial_config: { sales_mode: "immediate", allow_when_store_closed: false, require_scheduled_order: false, min_lead_minutes: 0, max_lead_days: null, allowed_payment_methods: [] },
  marketing_config: { planned_budget: null, traffic_campaign_id: null, attribution_window_days: 30 }, published_version: null, offers: [],
});

describe("strategic campaign visual document", () => {
  it("creates a complete editor document from an empty campaign", () => {
    const result = createStrategicCampaignVisualConfig(campaign({}));
    expect(result.schemaVersion).toBe(1);
    expect(result.whatsapp).toEqual({ enabled: false, url: "", label: "Fale conosco no WhatsApp" });
    expect(result.identity.brandName).toBe("Festival Gran Torino");
    expect(result.hero.title).toBe("Festival Gran Torino");
    expect(result.hero.titleLine1).toBe("Festival Gran");
    expect(result.hero.titleLine2).toBe("Torino");
    expect(result.header.ctaLabel).toBe("Visite a nossa loja");
    expect(result.offers.columns).toBe(2);
    expect(result.theme.accentColor).toBe("#d9a441");
    expect(result.hero).toMatchObject({ showTitle: true, imageDesktopUrl: "", imageMobileUrl: "", mediaFit: "contain" });
    expect(result.scrollIndicator).toEqual({ enabled: true, label: "Ver próxima oferta" });
  });

  it("keeps compatibility with the legacy flat visual fields", () => {
    const result = createStrategicCampaignVisualConfig(campaign({ heroTitle: "Título legado", heroImageUrl: "/legacy.webp", offersTitle: "Selecione", backgroundColor: "#000000" }));
    expect(result.hero.title).toBe("Título legado");
    expect(result.hero.imageDesktopUrl).toBe("/legacy.webp");
    expect(result.hero.imageMobileUrl).toBe("/legacy.webp");
    expect(result.offers.title).toBe("Selecione");
    expect(result.theme.backgroundColor).toBe("#000000");
  });

  it("prioritizes and serializes the structured C4 document", () => {
    const result = createStrategicCampaignVisualConfig(campaign({ heroTitle: "Legado", hero: { title: "C4", alignment: "left", overlay: 120 }, offers: { columns: 3, cardStyle: "outline" } }));
    expect(result.hero).toMatchObject({ title: "C4", alignment: "left", overlay: 90 });
    expect(result.offers).toMatchObject({ columns: 3, cardStyle: "outline" });
    expect(serializeStrategicCampaignVisualConfig(result)).toEqual(result);
  });

  it("normalizes responsive media and all optional landing blocks", () => {
    const result = createStrategicCampaignVisualConfig(campaign({
      identity: { logoDesktopUrl: "/logo-wide.webp", logoMobileUrl: "/logo-square.webp" },
      hero: { imageDesktopUrl: "/hero-desktop.webp", imageMobileUrl: "/hero-mobile.webp", videoMobileUrl: "/hero-mobile.mp4", height: "full" },
      complementary: { enabled: true, placement: "before_offers", imageSide: "right", imageDesktopUrl: "/about.webp" },
      information: { enabled: true, title: "Regras", body: "Consulte as condições." },
      scrollIndicator: { enabled: false },
      theme: { fontFamily: "serif", radius: "none", sectionSpacing: "wide" },
    }));
    expect(result.identity.logoMobileUrl).toBe("/logo-square.webp");
    expect(result.hero).toMatchObject({ imageDesktopUrl: "/hero-desktop.webp", imageMobileUrl: "/hero-mobile.webp", videoMobileUrl: "/hero-mobile.mp4", height: "full" });
    expect(result.complementary).toMatchObject({ enabled: true, placement: "before_offers", imageSide: "right" });
    expect(result.information.enabled).toBe(true);
    expect(result.scrollIndicator.enabled).toBe(false);
    expect(result.theme).toMatchObject({ fontFamily: "serif", radius: "none", sectionSpacing: "wide" });
  });

  it("normalizes the floating WhatsApp configuration", () => {
    const result = createStrategicCampaignVisualConfig(campaign({ whatsapp: { enabled: true, url: "https://wa.me/5511999999999?text=Ol%C3%A1", label: "Chame no WhatsApp" } }));
    expect(result.whatsapp).toEqual({ enabled: true, url: "https://wa.me/5511999999999?text=Ol%C3%A1", label: "Chame no WhatsApp" });
  });

  it("normalizes configurable two-line title, footer logo, and complementary link styling", () => {
    const result = createStrategicCampaignVisualConfig(campaign({
      identity: { logoDesktopUrl: "/brand.webp" },
      hero: { titleLine1: "Fim de semana", titleLine2: "Gran Torino" },
      complementary: { enabled: true, backgroundColor: "#22150f", url: "https://example.com/loja", linkLabel: "Conheça a loja" },
      footer: { logoUrl: "/footer.webp", showLogo: true },
    }));

    expect(result.hero).toMatchObject({ titleLine1: "Fim de semana", titleLine2: "Gran Torino" });
    expect(result.complementary).toMatchObject({ backgroundColor: "#22150f", linkUrl: "https://example.com/loja", linkLabel: "Conheça a loja" });
    expect(result.footer).toMatchObject({ showLogo: true, logoDesktopUrl: "/footer.webp", logoMobileUrl: "/footer.webp" });
  });
});
