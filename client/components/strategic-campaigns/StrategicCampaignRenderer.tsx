import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowRight, Clock3 } from "lucide-react";
import type { ApiStrategicCampaign, ApiStrategicOffer } from "@/lib/api";
import { resolveAssetUrl } from "@/lib/api";
import { createStrategicCampaignVisualConfig, type StrategicCampaignVisualConfig } from "./strategicCampaignVisual";

export type StrategicCampaignViewport = "desktop" | "tablet" | "mobile";
type Props = { campaign: ApiStrategicCampaign; config?: StrategicCampaignVisualConfig; mode?: "public" | "preview"; viewport?: StrategicCampaignViewport; onOfferSelect?: (offer: ApiStrategicOffer) => void; onScrollIndicatorClick?: () => void };

const price = (value: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
const fontFamilies = { system: "ui-sans-serif, system-ui, sans-serif", serif: "Georgia, Cambria, serif", rounded: "Nunito, ui-rounded, system-ui, sans-serif" } as const;
const radii = { none: "rounded-none", medium: "rounded-xl", large: "rounded-3xl" } as const;
const sectionSpacing = { compact: "py-8", normal: "py-14", wide: "py-20" } as const;
const heroHeights = { compact: "min-h-[360px]", normal: "min-h-[520px]", full: "min-h-[calc(100vh-64px)]" } as const;
const imageRatios = { landscape: "aspect-[16/9]", square: "aspect-square", portrait: "aspect-[4/5]" } as const;
const mediaFits = { cover: "object-cover", contain: "object-contain" } as const;
const mediaPositions = { center: "object-center", top: "object-top", bottom: "object-bottom" } as const;

function remainingParts(target: string | null, now: number) {
  if (!target) return null;
  const remaining = Math.max(0, new Date(target).getTime() - now);
  return { ended: remaining <= 0, days: Math.floor(remaining / 86_400_000), hours: Math.floor((remaining % 86_400_000) / 3_600_000), minutes: Math.floor((remaining % 3_600_000) / 60_000), seconds: Math.floor((remaining % 60_000) / 1000) };
}

export default function StrategicCampaignRenderer({ campaign, config, mode = "public", viewport, onOfferSelect, onScrollIndicatorClick }: Props) {
  const visual = config ?? createStrategicCampaignVisualConfig(campaign);
  const [now, setNow] = useState(() => Date.now());
  const [nextOfferIndex, setNextOfferIndex] = useState<number | null>(null);
  const offerRefs = useRef<Array<HTMLElement | null>>([]);
  const offers = useMemo(() => campaign.offers.filter((offer) => offer.active && !offer.archived_at).sort((a, b) => a.display_order - b.display_order), [campaign.offers]);
  const remaining = remainingParts(campaign.ends_at, now);

  useEffect(() => {
    if (!visual.countdown.enabled || !campaign.ends_at) return;
    const timer = window.setInterval(() => setNow(Date.now()), visual.countdown.showSeconds ? 1_000 : 60_000);
    return () => window.clearInterval(timer);
  }, [campaign.ends_at, visual.countdown.enabled, visual.countdown.showSeconds]);

  useEffect(() => {
    if (!visual.scrollIndicator.enabled || offers.length < 2) { setNextOfferIndex(null); return; }
    const update = () => {
      const boundary = window.innerHeight * 0.82;
      const next = offerRefs.current.findIndex((node) => Boolean(node && node.getBoundingClientRect().top > boundary));
      setNextOfferIndex(next >= 0 ? next : null);
    };
    update();
    window.addEventListener("scroll", update, { passive: true }); window.addEventListener("resize", update);
    const observer = new ResizeObserver(update); offerRefs.current.forEach((node) => node && observer.observe(node));
    return () => { window.removeEventListener("scroll", update); window.removeEventListener("resize", update); observer.disconnect(); };
  }, [offers.length, visual.scrollIndicator.enabled, viewport]);

  const align = visual.hero.alignment === "left" ? "items-start text-left" : "items-center text-center";
  const columns = visual.offers.columns === 1 ? "grid-cols-1" : visual.offers.columns === 3 ? "md:grid-cols-2 xl:grid-cols-3" : "md:grid-cols-2";
  const logoSize = visual.header.logoSize === "small" ? "h-7 max-w-28" : visual.header.logoSize === "large" ? "h-14 max-w-48" : "h-10 max-w-36";
  const headerPadding = visual.header.spacing === "compact" ? "py-2" : visual.header.spacing === "wide" ? "py-5" : "py-3";
  const rootRadius = radii[visual.theme.radius];
  const publicResponsive = mode === "public" && !viewport;
  const scrollToOffers = () => document.getElementById(`strategic-offers-${mode}`)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  const scrollNext = () => { if (nextOfferIndex == null) return; onScrollIndicatorClick?.(); offerRefs.current[nextOfferIndex]?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" }); };

  const complementary = <ComplementarySection visual={visual} viewport={viewport} publicResponsive={publicResponsive} rootRadius={rootRadius} />;
  return <div className="relative min-h-full overflow-hidden" style={{ background: visual.theme.backgroundColor, color: visual.theme.textColor, fontFamily: fontFamilies[visual.theme.fontFamily] }} data-testid={`strategic-campaign-renderer-${mode}`}>
    {visual.header.enabled && <header className={`${visual.header.sticky && mode === "public" ? "sticky top-0 z-30" : "relative z-20"} border-b border-white/10 backdrop-blur`} style={{ backgroundColor: visual.header.backgroundColor || `${visual.theme.backgroundColor}ee` }}>
      <div className={`mx-auto flex max-w-6xl items-center gap-4 px-5 ${headerPadding} ${visual.header.alignment === "center" ? "justify-center" : "justify-between"}`}>
        <div className="flex min-w-0 items-center gap-3">
          {(visual.identity.logoDesktopUrl || visual.identity.logoMobileUrl) && <picture><source media="(max-width: 640px)" srcSet={resolveAssetUrl(visual.identity.logoMobileUrl || visual.identity.logoDesktopUrl)} /><img src={resolveAssetUrl(visual.identity.logoDesktopUrl || visual.identity.logoMobileUrl)} alt={visual.identity.brandName} className={`${logoSize} w-auto object-contain`} /></picture>}
          {visual.header.showBrandName && <strong className="truncate text-sm">{visual.identity.brandName}</strong>}
        </div>
        {visual.header.alignment !== "center" && <button type="button" onClick={scrollToOffers} className="rounded-full px-4 py-2 text-xs font-bold" style={{ background: visual.theme.accentColor, color: visual.theme.backgroundColor }}>{visual.header.ctaLabel}</button>}
      </div>
    </header>}

    {visual.hero.enabled && <section className={`relative flex flex-col justify-center overflow-hidden px-6 py-16 ${heroHeights[visual.hero.height]} ${align}`}>
      <HeroMedia visual={visual} viewport={viewport} publicResponsive={publicResponsive} />
      {(visual.hero.imageDesktopUrl || visual.hero.imageMobileUrl || visual.hero.videoDesktopUrl || visual.hero.videoMobileUrl) && <div className="absolute inset-0 bg-black" style={{ opacity: visual.hero.overlay / 100 }} />}
      <div className={`relative mx-auto flex w-full max-w-5xl flex-col ${align}`}>
        {visual.hero.showEyebrow && <span className="mb-4 text-xs font-bold uppercase tracking-[0.24em]" style={{ color: visual.theme.accentColor }}>{visual.identity.eyebrow}</span>}
        {visual.hero.showTitle && <h1 className="max-w-4xl text-4xl font-black leading-tight sm:text-5xl lg:text-6xl">{visual.hero.title}</h1>}
        {visual.hero.showSubtitle && <p className="mt-5 max-w-2xl text-base opacity-80 sm:text-lg">{visual.hero.subtitle}</p>}
        {visual.countdown.enabled && remaining && <Countdown visual={visual} remaining={remaining} />}
      </div>
    </section>}

    {visual.complementary.enabled && visual.complementary.placement === "before_offers" && complementary}
    <section id={`strategic-offers-${mode}`} className={`mx-auto max-w-6xl scroll-mt-20 px-5 ${sectionSpacing[visual.theme.sectionSpacing]}`}>
      {visual.offers.showHeading && <div className="text-center"><h2 className="text-3xl font-black">{visual.offers.title}</h2><p className="mt-2 opacity-70">{visual.offers.subtitle}</p></div>}
      {offers.length ? <div className={`${visual.offers.showHeading ? "mt-8" : ""} grid gap-5 ${columns}`}>{offers.map((offer, index) => <article ref={(node) => { offerRefs.current[index] = node; }} data-strategic-offer-card key={offer.id} className={`overflow-hidden border ${rootRadius} ${visual.offers.cardStyle === "outline" ? "bg-transparent" : "border-transparent"}`} style={{ background: visual.offers.cardStyle === "soft" ? visual.theme.surfaceColor : undefined, borderColor: offer.highlighted ? visual.theme.accentColor : "rgba(255,255,255,.14)" }}>
        {(offer.image_mobile_url || offer.image_desktop_url) && <picture><source media="(max-width: 640px)" srcSet={resolveAssetUrl(offer.image_mobile_url || offer.image_desktop_url || "")} /><img src={resolveAssetUrl(offer.image_desktop_url || offer.image_mobile_url || "")} alt={offer.title} loading={index < 2 ? "eager" : "lazy"} className={`${imageRatios[visual.offers.imageRatio]} w-full object-cover`} /></picture>}
        <div className="p-5">{offer.badge_text && <span className="rounded-full px-2.5 py-1 text-xs font-bold" style={{ background: visual.theme.accentColor, color: visual.theme.backgroundColor }}>{offer.badge_text}</span>}<h3 className="mt-3 text-xl font-black">{offer.title}</h3>{offer.description && <p className="mt-2 text-sm opacity-70">{offer.description}</p>}<div className="mt-6 flex flex-wrap items-end justify-between gap-3"><div>{offer.price_original > offer.price_promotional && <span className="block text-xs line-through opacity-50">{price(offer.price_original)}</span>}<strong className="text-2xl" style={{ color: visual.theme.accentColor }}>{price(offer.price_promotional)}</strong></div><button type="button" disabled={mode === "preview" || (!offer.product_id && !offer.kit_id)} onClick={() => onOfferSelect?.(offer)} className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-black disabled:cursor-default disabled:opacity-70" style={{ background: visual.theme.accentColor, color: visual.theme.backgroundColor }}>{offer.button_text || "Comprar"}<ArrowRight className="h-4 w-4" /></button></div></div>
      </article>)}</div> : <div className={`border border-dashed border-white/20 p-10 text-center text-sm opacity-60 ${rootRadius} ${visual.offers.showHeading ? "mt-8" : ""}`}>Adicione e ative ofertas para preencher esta seção.</div>}
    </section>
    {visual.complementary.enabled && visual.complementary.placement === "after_offers" && complementary}
    {visual.information.enabled && <section className={`mx-auto max-w-4xl px-5 ${sectionSpacing[visual.theme.sectionSpacing]}`}><div className={`border border-white/10 p-6 sm:p-8 ${rootRadius}`} style={{ background: visual.theme.surfaceColor }}><h2 className="text-2xl font-black">{visual.information.title}</h2><p className="mt-4 whitespace-pre-line text-sm leading-7 opacity-75">{visual.information.body}</p></div></section>}
    {visual.footer.enabled && <footer className="border-t border-white/10 px-5 py-10 text-center"><p className="font-semibold">{visual.footer.text}</p><p className="mt-2 text-xs opacity-50">{visual.footer.legalText}</p></footer>}
    {visual.scrollIndicator.enabled && nextOfferIndex !== null && <button type="button" onClick={scrollNext} aria-label={visual.scrollIndicator.label} title={visual.scrollIndicator.label} className={`${mode === "public" ? "fixed bottom-6 right-6" : "sticky bottom-4 ml-auto mr-4"} z-40 flex h-12 w-12 items-center justify-center rounded-full shadow-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 motion-safe:animate-bounce`} style={{ background: visual.theme.accentColor, color: visual.theme.backgroundColor }}><ArrowDown aria-hidden="true" /></button>}
  </div>;
}

function HeroMedia({ visual, viewport, publicResponsive }: { visual: StrategicCampaignVisualConfig; viewport?: StrategicCampaignViewport; publicResponsive: boolean }) {
  const mobile = viewport === "mobile"; const fit = visual.hero.mediaFit; const position = visual.hero.mediaPosition;
  const mediaClass = `absolute inset-0 h-full w-full ${mediaFits[fit]} ${mediaPositions[position]}`;
  const desktopVideo = visual.hero.videoDesktopUrl || visual.hero.videoMobileUrl; const mobileVideo = visual.hero.videoMobileUrl || visual.hero.videoDesktopUrl;
  if (publicResponsive && (desktopVideo || mobileVideo)) return <><video autoPlay muted loop playsInline preload="metadata" poster={resolveOptional(visual.hero.videoPosterDesktopUrl)} src={resolveAssetUrl(desktopVideo)} className={`${mediaClass} hidden sm:block`} /><video autoPlay muted loop playsInline preload="metadata" poster={resolveOptional(visual.hero.videoPosterMobileUrl || visual.hero.videoPosterDesktopUrl)} src={resolveAssetUrl(mobileVideo)} className={`${mediaClass} sm:hidden`} /></>;
  const video = mobile ? mobileVideo : desktopVideo;
  if (video) return <video autoPlay muted loop playsInline preload="metadata" poster={resolveOptional(mobile ? visual.hero.videoPosterMobileUrl || visual.hero.videoPosterDesktopUrl : visual.hero.videoPosterDesktopUrl)} src={resolveAssetUrl(video)} className={mediaClass} />;
  const desktopImage = visual.hero.imageDesktopUrl || visual.hero.imageMobileUrl; const mobileImage = visual.hero.imageMobileUrl || visual.hero.imageDesktopUrl;
  if (!desktopImage && !mobileImage) return null;
  if (publicResponsive) return <picture><source media="(max-width: 640px)" srcSet={resolveAssetUrl(mobileImage)} /><img src={resolveAssetUrl(desktopImage)} alt="" className={mediaClass} /></picture>;
  return <img src={resolveAssetUrl(mobile ? mobileImage : desktopImage)} alt="" className={mediaClass} />;
}

function ComplementarySection({ visual, viewport, publicResponsive, rootRadius }: { visual: StrategicCampaignVisualConfig; viewport?: StrategicCampaignViewport; publicResponsive: boolean; rootRadius: string }) {
  const desktop = visual.complementary.imageDesktopUrl || visual.complementary.imageMobileUrl; const mobile = visual.complementary.imageMobileUrl || visual.complementary.imageDesktopUrl;
  const image = desktop || mobile ? publicResponsive ? <picture><source media="(max-width: 640px)" srcSet={resolveAssetUrl(mobile)} /><img src={resolveAssetUrl(desktop)} alt="" className={`max-h-96 w-full object-cover ${rootRadius}`} /></picture> : <img src={resolveAssetUrl(viewport === "mobile" ? mobile : desktop)} alt="" className={`max-h-96 w-full object-cover ${rootRadius}`} /> : null;
  return <section className={`mx-auto grid max-w-6xl items-center gap-8 px-5 ${sectionSpacing[visual.theme.sectionSpacing]} md:grid-cols-2`}>{visual.complementary.imageSide === "left" ? image : null}<div><h2 className="text-3xl font-black">{visual.complementary.title}</h2><p className="mt-4 whitespace-pre-line leading-7 opacity-75">{visual.complementary.body}</p></div>{visual.complementary.imageSide === "right" ? image : null}</section>;
}

function Countdown({ visual, remaining }: { visual: StrategicCampaignVisualConfig; remaining: NonNullable<ReturnType<typeof remainingParts>> }) {
  if (remaining.ended) return <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/20 px-4 py-2 text-sm"><Clock3 className="h-4 w-4" style={{ color: visual.theme.accentColor }} /><strong>Encerrada</strong></div>;
  const units = [...(visual.countdown.showDays ? [[remaining.days, "dias"]] as const : []), [remaining.hours, "horas"] as const, [remaining.minutes, "min"] as const, ...(visual.countdown.showSeconds ? [[remaining.seconds, "seg"]] as const : [])];
  return <div className="mt-6 rounded-2xl border border-white/15 bg-black/25 px-4 py-3 backdrop-blur"><div className="flex items-center gap-2 text-xs opacity-75"><Clock3 className="h-4 w-4" style={{ color: visual.theme.accentColor }} />{visual.countdown.label}</div><div className="mt-2 flex flex-wrap gap-3">{units.map(([value, label]) => <span key={label}><strong className="text-xl">{String(value).padStart(2, "0")}</strong><small className="ml-1 opacity-60">{label}</small></span>)}</div></div>;
}

const resolveOptional = (value: string) => value ? resolveAssetUrl(value) : undefined;
