import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Clock, Flame, Gift, Truck } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import {
  promotionLandingsApi,
  productsApi,
  type ApiProduct,
  type ApiPromotionLandingPage,
  isAssetUrl,
  resolveAssetUrl,
} from "@/lib/api";
import { getTrackingData, trackEvent } from "@/lib/tracking";

type LandingMediaSlot = "image_url" | "image_url_2" | "video_url";
const DEFAULT_MEDIA_ORDER: LandingMediaSlot[] = ["image_url", "image_url_2", "video_url"];
const normalizeMediaOrder = (order?: LandingMediaSlot[] | null) => {
  const unique = (order || []).filter((slot, index, all) =>
    DEFAULT_MEDIA_ORDER.includes(slot) && all.indexOf(slot) === index
  );
  return [...unique, ...DEFAULT_MEDIA_ORDER.filter((slot) => !unique.includes(slot))];
};

const alignClass: Record<string, string> = {
  left: "items-start text-left",
  center: "items-center text-center",
  right: "items-end text-right",
};

const imagePositionClass: Record<string, string> = {
  center: "object-center",
  top: "object-top",
  bottom: "object-bottom",
  left: "object-left",
  right: "object-right",
};

const overlayClass: Record<string, string> = {
  "dark-gradient": "bg-gradient-to-t from-black via-black/60 to-black/20",
  dark: "bg-black/65",
  light: "bg-white/30",
  brand: "bg-gradient-to-t from-brand-dark via-brand-dark/70 to-gold/20",
};

type LandingMedia = {
  type: "image" | "video";
  url: string;
  slot: LandingMediaSlot;
};

const advanceIntervalMs = {
  image: 4500,
  video: 15000,
};
const FREE_SHIPPING_LABEL = "Frete Grátis na Promoção";

const freeShippingLabel = (value?: string | null) => {
  const normalized = value?.trim();
  const comparable = normalized
    ?.toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  if (!normalized || comparable === "frete gratis na promocao") {
    return FREE_SHIPPING_LABEL;
  }
  return normalized;
};

export default function PromocaoLanding() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [landing, setLanding] = useState<ApiPromotionLandingPage | null>(null);
  const [product, setProduct] = useState<ApiProduct | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeMediaIndex, setActiveMediaIndex] = useState(0);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setError("");
    promotionLandingsApi.getBySlug(slug)
      .then(async (page) => {
        setLanding(page);
        const prod = await productsApi.get(page.product_id);
        setProduct(prod);
        const td = getTrackingData();
        trackEvent("landing_promo_view", undefined, {
          product_id: page.product_id,
          promotion_id: page.promotion_id,
          landing_page_id: page.id,
          source: td.referrer || document.referrer || "direct",
          session_id: td.session_id,
          timestamp: new Date().toISOString(),
        });
      })
      .catch(() => setError("Promocao nao encontrada ou fora do horario."))
      .finally(() => setLoading(false));
  }, [slug]);

  const mediaItems = useMemo<LandingMedia[]>(() => {
    const mediaBySlot: Partial<Record<LandingMediaSlot, LandingMedia>> = {};
    if (landing?.image_url) mediaBySlot.image_url = { type: "image", url: resolveAssetUrl(landing.image_url), slot: "image_url" };
    if (landing?.image_url_2) mediaBySlot.image_url_2 = { type: "image", url: resolveAssetUrl(landing.image_url_2), slot: "image_url_2" };
    if (landing?.video_url) mediaBySlot.video_url = { type: "video", url: resolveAssetUrl(landing.video_url), slot: "video_url" };
    const items = normalizeMediaOrder(landing?.media_order).flatMap((slot) => mediaBySlot[slot] ? [mediaBySlot[slot]!] : []);
    if (items.length === 0 && isAssetUrl(product?.icon)) {
      items.push({ type: "image", url: resolveAssetUrl(product?.icon), slot: "image_url" });
    }
    return items;
  }, [landing?.image_url, landing?.image_url_2, landing?.video_url, landing?.media_order, product?.icon]);

  const activeMedia = mediaItems[activeMediaIndex % Math.max(mediaItems.length, 1)];
  const hasCarousel = mediaItems.length > 1;

  useEffect(() => {
    setActiveMediaIndex(0);
  }, [landing?.id]);

  useEffect(() => {
    if (!hasCarousel || !activeMedia) return;
    const timer = window.setTimeout(() => {
      setActiveMediaIndex((index) => (index + 1) % mediaItems.length);
    }, advanceIntervalMs[activeMedia.type]);
    return () => window.clearTimeout(timer);
  }, [activeMedia?.type, activeMediaIndex, hasCarousel, mediaItems.length]);

  const changeMedia = (direction: 1 | -1) => {
    if (!hasCarousel) return;
    setActiveMediaIndex((index) => (index + direction + mediaItems.length) % mediaItems.length);
  };

  const cta = () => {
    if (!landing) return;
    const td = getTrackingData();
    trackEvent("landing_promo_cta_click", undefined, {
      product_id: landing.product_id,
      promotion_id: landing.promotion_id,
      landing_page_id: landing.id,
      source: td.referrer || document.referrer || "direct",
      session_id: td.session_id,
      timestamp: new Date().toISOString(),
    });
    navigate(`/product/${landing.product_id}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-00 flex items-center justify-center">
        <div className="text-gold text-sm font-semibold animate-pulse">Carregando promocao...</div>
      </div>
    );
  }

  if (error || !landing) {
    return (
      <div className="min-h-screen bg-surface-00 flex flex-col items-center justify-center gap-4 px-5 text-center">
        <p className="text-cream text-lg font-bold">Promocao indisponivel</p>
        <p className="text-stone text-sm">{error}</p>
        <button onClick={() => navigate("/cardapio")} className="bg-gold hover:bg-gold/90 text-cream font-bold py-3 px-6 rounded-full transition-colors">
          Voltar ao cardapio
        </button>
      </div>
    );
  }

  const alignment = alignClass[landing.content_alignment] ?? alignClass.center;
  const position = imagePositionClass[landing.image_position] ?? imagePositionClass.center;
  const overlay = overlayClass[landing.overlay_style] ?? overlayClass["dark-gradient"];
  const giftText = product?.promotion_gift_name
    ? `${landing.gift_label_prefix || "Brinde"}: ${product.promotion_gift_name}`
    : landing.gift_fallback_label || "Brinde incluído";
  const promoBenefits = [
    product?.promotion_free_shipping ? { icon: Truck, text: freeShippingLabel(landing.free_shipping_label) } : null,
    product?.promotion_gift_enabled ? { icon: Gift, text: giftText } : null,
    landing.promotion_active_now ? { icon: Clock, text: landing.active_offer_label || "Oferta ativa agora" } : null,
  ].filter(Boolean) as { icon: typeof Truck; text: string }[];

  return (
    <div className="min-h-screen bg-surface-00 text-cream">
      <main className="relative min-h-screen overflow-hidden">
        {activeMedia ? (
          activeMedia.type === "video" ? (
            <video
              key={`${activeMedia.url}-${activeMediaIndex}`}
              src={activeMedia.url}
              className={`absolute inset-0 h-full w-full object-cover ${position}`}
              muted
              playsInline
              autoPlay
              loop={false}
            />
          ) : (
          <img
            key={`${activeMedia.url}-${activeMediaIndex}`}
            src={activeMedia.url}
            alt={landing.title}
            className={`absolute inset-0 h-full w-full object-cover ${position}`}
          />
          )
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-brand-dark via-surface-02 to-surface-00" />
        )}
        <div className={`absolute inset-0 ${overlay}`} />

        {hasCarousel && (
          <>
            <button
              type="button"
              onClick={() => changeMedia(-1)}
              className="absolute left-3 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-white/15 bg-black/35 text-cream shadow-lg backdrop-blur transition-colors hover:bg-black/50"
              aria-label="Mídia anterior"
            >
              <ChevronLeft size={24} />
            </button>
            <button
              type="button"
              onClick={() => changeMedia(1)}
              className="absolute right-3 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-white/15 bg-black/35 text-cream shadow-lg backdrop-blur transition-colors hover:bg-black/50"
              aria-label="Próxima mídia"
            >
              <ChevronRight size={24} />
            </button>
            <div className="absolute bottom-24 left-1/2 z-20 flex -translate-x-1/2 gap-2">
              {mediaItems.map((item, index) => (
                <button
                  key={`${item.type}-${item.url}`}
                  type="button"
                  onClick={() => setActiveMediaIndex(index)}
                  className={`h-2 rounded-full transition-all ${index === activeMediaIndex ? "w-7 bg-gold" : "w-2 bg-white/50"}`}
                  aria-label={`Mostrar mídia ${index + 1}`}
                />
              ))}
            </div>
          </>
        )}

        <header className="relative z-10 flex items-center justify-between px-4 py-4">
          <button
            onClick={() => navigate("/cardapio")}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-black/35 text-cream backdrop-blur"
            aria-label="Voltar para o cardapio"
          >
            <ChevronLeft size={22} />
          </button>
          <button onClick={() => navigate("/")} aria-label="Ir para a home da loja">
            <MoschettieriLogo className="text-cream text-base scale-[1.12] origin-center drop-shadow" />
          </button>
          <div className="h-10 w-10" />
        </header>

        <section className={`relative z-10 flex min-h-[calc(100vh-72px)] flex-col justify-end px-5 pb-28 pt-6 ${alignment}`}>
          <div className={`flex max-w-xl flex-col gap-4 ${alignment}`}>
            <div className="inline-flex items-center gap-2 rounded-full border border-gold/40 bg-black/35 px-3 py-1.5 text-xs font-bold uppercase tracking-wide text-gold backdrop-blur">
              <Flame size={14} />
              {landing.badge_text || "Oferta do dia"}
            </div>

            <div className="space-y-3">
              <h1 className="text-4xl font-black leading-[0.95] text-cream drop-shadow sm:text-5xl">
                {landing.title}
              </h1>
              {landing.subtitle && (
                <p className="max-w-md text-lg font-semibold leading-snug text-parchment drop-shadow">
                  {landing.subtitle}
                </p>
              )}
              {landing.description && (
                <p className="max-w-md text-sm leading-relaxed text-stone drop-shadow">
                  {landing.description}
                </p>
              )}
            </div>

            {promoBenefits.length > 0 && (
              <div className={`flex flex-wrap gap-2 ${landing.content_alignment === "right" ? "justify-end" : landing.content_alignment === "center" ? "justify-center" : "justify-start"}`}>
                {promoBenefits.map(({ icon: Icon, text }) => (
                  <span key={text} className="inline-flex items-center gap-1.5 rounded-full bg-black/35 px-3 py-1.5 text-xs font-semibold text-parchment backdrop-blur">
                    <Icon size={13} className="text-gold" />
                    {text}
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>

        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-white/10 bg-brand-dark/92 px-4 py-3 pb-[calc(env(safe-area-inset-bottom)+12px)] backdrop-blur">
          <div className="mx-auto flex max-w-xl items-center gap-3">
            <button
              onClick={() => navigate("/cardapio")}
              className="h-12 w-12 shrink-0 rounded-full border border-surface-03 bg-surface-02 text-parchment"
              aria-label="Voltar"
            >
              <ChevronLeft size={20} className="mx-auto" />
            </button>
            <button
              onClick={cta}
              className="h-12 flex-1 rounded-full bg-gold px-5 text-sm font-black uppercase tracking-wide text-cream shadow-lg shadow-gold/30 active:scale-[0.98]"
            >
              {landing.cta_text || "Quero essa pizza"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
