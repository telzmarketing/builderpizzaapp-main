import type { ApiStrategicCampaign } from "@/lib/api";

export type StrategicCampaignVisualConfig = {
  schemaVersion: 1;
  identity: { brandName: string; eyebrow: string; logoDesktopUrl: string; logoMobileUrl: string };
  header: { enabled: boolean; sticky: boolean; showBrandName: boolean; ctaLabel: string; alignment: "left" | "center"; logoSize: "small" | "medium" | "large"; backgroundColor: string; spacing: "compact" | "normal" | "wide" };
  hero: { enabled: boolean; showEyebrow: boolean; showTitle: boolean; showSubtitle: boolean; title: string; subtitle: string; imageDesktopUrl: string; imageMobileUrl: string; videoDesktopUrl: string; videoMobileUrl: string; videoPosterDesktopUrl: string; videoPosterMobileUrl: string; alignment: "left" | "center"; overlay: number; height: "compact" | "normal" | "full"; mediaFit: "cover" | "contain"; mediaPosition: "center" | "top" | "bottom" };
  countdown: { enabled: boolean; label: string; showDays: boolean; showSeconds: boolean };
  offers: { title: string; subtitle: string; showHeading: boolean; columns: 1 | 2 | 3; cardStyle: "soft" | "outline"; imageRatio: "landscape" | "square" | "portrait" };
  complementary: { enabled: boolean; title: string; body: string; imageDesktopUrl: string; imageMobileUrl: string; placement: "before_offers" | "after_offers"; imageSide: "left" | "right" };
  information: { enabled: boolean; title: string; body: string };
  scrollIndicator: { enabled: boolean; label: string };
  footer: { enabled: boolean; text: string; legalText: string };
  theme: { backgroundColor: string; surfaceColor: string; textColor: string; accentColor: string; fontFamily: "system" | "serif" | "rounded"; radius: "none" | "medium" | "large"; sectionSpacing: "compact" | "normal" | "wide" };
};

type UnknownRecord = Record<string, unknown>;
const record = (value: unknown): UnknownRecord => value && typeof value === "object" && !Array.isArray(value) ? value as UnknownRecord : {};
const text = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const bool = (value: unknown, fallback: boolean) => typeof value === "boolean" ? value : fallback;
const number = (value: unknown, fallback: number) => typeof value === "number" && Number.isFinite(value) ? value : fallback;
const oneOf = <T extends string>(value: unknown, allowed: readonly T[], fallback: T): T => allowed.includes(value as T) ? value as T : fallback;

export function createStrategicCampaignVisualConfig(campaign: Pick<ApiStrategicCampaign, "name" | "commercial_name" | "description" | "visual_config">): StrategicCampaignVisualConfig {
  const raw = record(campaign.visual_config);
  const identity = record(raw.identity); const header = record(raw.header); const hero = record(raw.hero); const countdown = record(raw.countdown);
  const offers = record(raw.offers); const complementary = record(raw.complementary); const information = record(raw.information);
  const scrollIndicator = record(raw.scrollIndicator); const footer = record(raw.footer); const theme = record(raw.theme);
  const legacyLogo = text(identity.logoUrl); const legacyHeroImage = text(hero.imageUrl, text(raw.heroImageUrl));
  const legacyHeroVideo = text(hero.videoUrl, text(raw.heroVideoUrl)); const legacyComplementaryImage = text(complementary.imageUrl);
  const columns = number(offers.columns, 2);
  return {
    schemaVersion: 1,
    identity: { brandName: text(identity.brandName, campaign.commercial_name || campaign.name), eyebrow: text(identity.eyebrow, text(raw.headerText, "Oferta especial")), logoDesktopUrl: text(identity.logoDesktopUrl, legacyLogo), logoMobileUrl: text(identity.logoMobileUrl, legacyLogo) },
    header: { enabled: bool(header.enabled, true), sticky: bool(header.sticky, true), showBrandName: bool(header.showBrandName, true), ctaLabel: text(header.ctaLabel, "Ver ofertas"), alignment: oneOf(header.alignment, ["left", "center"] as const, "left"), logoSize: oneOf(header.logoSize, ["small", "medium", "large"] as const, "medium"), backgroundColor: text(header.backgroundColor), spacing: oneOf(header.spacing, ["compact", "normal", "wide"] as const, "normal") },
    hero: { enabled: bool(hero.enabled, true), showEyebrow: bool(hero.showEyebrow, true), showTitle: bool(hero.showTitle, true), showSubtitle: bool(hero.showSubtitle, true), title: text(hero.title, text(raw.heroTitle, campaign.commercial_name || campaign.name)), subtitle: text(hero.subtitle, text(raw.heroSubtitle, campaign.description || "Escolha sua oferta.")), imageDesktopUrl: text(hero.imageDesktopUrl, legacyHeroImage), imageMobileUrl: text(hero.imageMobileUrl, legacyHeroImage), videoDesktopUrl: text(hero.videoDesktopUrl, legacyHeroVideo), videoMobileUrl: text(hero.videoMobileUrl, legacyHeroVideo), videoPosterDesktopUrl: text(hero.videoPosterDesktopUrl), videoPosterMobileUrl: text(hero.videoPosterMobileUrl), alignment: oneOf(hero.alignment, ["left", "center"] as const, "center"), overlay: Math.min(90, Math.max(0, number(hero.overlay, 45))), height: oneOf(hero.height, ["compact", "normal", "full"] as const, "normal"), mediaFit: oneOf(hero.mediaFit, ["cover", "contain"] as const, "cover"), mediaPosition: oneOf(hero.mediaPosition, ["center", "top", "bottom"] as const, "center") },
    countdown: { enabled: bool(countdown.enabled, true), label: text(countdown.label, "Oferta válida por tempo limitado"), showDays: bool(countdown.showDays, true), showSeconds: bool(countdown.showSeconds, false) },
    offers: { title: text(offers.title, text(raw.offersTitle, "Ofertas disponíveis")), subtitle: text(offers.subtitle, "Escolha a opção ideal para você."), showHeading: bool(offers.showHeading, true), columns: columns === 1 || columns === 3 ? columns : 2, cardStyle: oneOf(offers.cardStyle, ["soft", "outline"] as const, "soft"), imageRatio: oneOf(offers.imageRatio, ["landscape", "square", "portrait"] as const, "landscape") },
    complementary: { enabled: bool(complementary.enabled, false), title: text(complementary.title), body: text(complementary.body), imageDesktopUrl: text(complementary.imageDesktopUrl, legacyComplementaryImage), imageMobileUrl: text(complementary.imageMobileUrl, legacyComplementaryImage), placement: oneOf(complementary.placement, ["before_offers", "after_offers"] as const, "after_offers"), imageSide: oneOf(complementary.imageSide, ["left", "right"] as const, "left") },
    information: { enabled: bool(information.enabled, false), title: text(information.title, "Informações importantes"), body: text(information.body) },
    scrollIndicator: { enabled: bool(scrollIndicator.enabled, true), label: text(scrollIndicator.label, "Ver próxima oferta") },
    footer: { enabled: bool(footer.enabled, true), text: text(footer.text, text(raw.footerText)), legalText: text(footer.legalText, "Condições sujeitas à disponibilidade.") },
    theme: { backgroundColor: text(theme.backgroundColor, text(raw.backgroundColor, "#17120f")), surfaceColor: text(theme.surfaceColor, "#241b16"), textColor: text(theme.textColor, text(raw.textColor, "#fff7ed")), accentColor: text(theme.accentColor, text(raw.accentColor, "#d9a441")), fontFamily: oneOf(theme.fontFamily, ["system", "serif", "rounded"] as const, "system"), radius: oneOf(theme.radius, ["none", "medium", "large"] as const, "large"), sectionSpacing: oneOf(theme.sectionSpacing, ["compact", "normal", "wide"] as const, "normal") },
  };
}

export function serializeStrategicCampaignVisualConfig(config: StrategicCampaignVisualConfig): Record<string, unknown> {
  return config as unknown as Record<string, unknown>;
}
