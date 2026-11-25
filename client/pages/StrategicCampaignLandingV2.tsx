import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, Clock } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { productsApi, strategicCampaignsApi, type ApiProduct, type ApiStrategicCampaign } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { captureTrackingFromUrl, trackEvent } from "@/lib/tracking";

type VisualConfig = { backgroundColor?: string; textColor?: string; accentColor?: string; headerText?: string; heroTitle?: string; heroSubtitle?: string; heroImageUrl?: string; heroVideoUrl?: string; offersTitle?: string; footerText?: string };

export default function StrategicCampaignLandingV2() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { addToCart } = useApp();
  const [campaign, setCampaign] = useState<ApiStrategicCampaign | null>(null);
  const [products, setProducts] = useState<Record<string, ApiProduct>>({});
  const [error, setError] = useState("");
  const [showScrollHint, setShowScrollHint] = useState(false);
  const offersRef = useRef<HTMLElement | null>(null);
  const firstOfferRef = useRef<HTMLElement | null>(null);
  const lastOfferRef = useRef<HTMLElement | null>(null);
  const trackedViewRef = useRef<string | null>(null);
  const visual = (campaign?.visual_config ?? {}) as VisualConfig;
  const offers = useMemo(() => campaign?.offers.filter((offer) => offer.active) ?? [], [campaign]);

  useEffect(() => { captureTrackingFromUrl(); }, []);

  useEffect(() => {
    if (!slug) return;
    setError("");
    strategicCampaignsApi.publicBySlug(slug).then(async (data) => {
      setCampaign(data);
      if (trackedViewRef.current !== data.id) {
        trackedViewRef.current = data.id;
        trackEvent("strategic_campaign_view", undefined, { campaign_id: data.id, campaign_slug: data.slug });
      }
      const ids = data.offers.flatMap((offer) => offer.product_id ? [offer.product_id] : []);
      const entries = await Promise.all(ids.map(async (id) => [id, await productsApi.get(id)] as const));
      setProducts(Object.fromEntries(entries));
    }).catch(() => setError("Campanha não encontrada ou encerrada."));
  }, [slug]);

  useEffect(() => {
    const last = lastOfferRef.current;
    const section = offersRef.current;
    if (!last || !section || offers.length < 2) { setShowScrollHint(false); return; }
    const update = () => setShowScrollHint(last.getBoundingClientRect().bottom > window.innerHeight + 8);
    update();
    const observer = new IntersectionObserver(update, { threshold: 0.05 });
    const resizeObserver = new ResizeObserver(update);
    observer.observe(last); resizeObserver.observe(section);
    window.addEventListener("scroll", update, { passive: true }); window.addEventListener("resize", update);
    return () => { observer.disconnect(); resizeObserver.disconnect(); window.removeEventListener("scroll", update); window.removeEventListener("resize", update); };
  }, [offers.length]);

  const scrollToOffers = () => {
    trackEvent("strategic_campaign_scroll_to_offers", undefined, { campaign_id: campaign?.id, campaign_slug: slug });
    firstOfferRef.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  };

  if (error) return <div className="flex min-h-screen items-center justify-center bg-surface-00 p-6 text-center text-cream"><div><p className="text-xl font-bold">{error}</p><button onClick={() => navigate("/")} className="mt-4 rounded-lg bg-gold px-4 py-2">Voltar</button></div></div>;
  if (!campaign) return <div className="flex min-h-screen items-center justify-center bg-surface-00 text-gold" role="status">Carregando campanha...</div>;

  const background = String(visual.backgroundColor || "#17120f");
  const color = String(visual.textColor || "#fff7ed");
  const accent = String(visual.accentColor || "#d9a441");
  return <main className="min-h-screen" style={{ background, color }}>
    <header className="sticky top-0 z-10 border-b border-white/10 p-4" style={{ background, color: accent }}><button onClick={() => navigate(-1)} aria-label="Voltar" className="rounded p-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"><ArrowLeft /></button><span className="ml-4 font-semibold">{String(visual.headerText || campaign.commercial_name || campaign.name)}</span></header>
    <section className="mx-auto max-w-5xl px-4 pb-10 pt-8 text-center">
      {visual.heroImageUrl && <img src={String(visual.heroImageUrl)} alt="" className="mx-auto mb-6 max-h-80 w-full rounded-2xl object-cover" loading="eager" decoding="async" onError={(event) => { event.currentTarget.hidden = true; }} />}
      {visual.heroVideoUrl && <video controls preload="metadata" className="mx-auto mb-6 max-h-80 w-full rounded-2xl" src={visual.heroVideoUrl} onError={(event) => { event.currentTarget.hidden = true; }} />}
      <h1 className="text-4xl font-black" style={{ color: accent }}>{String(visual.heroTitle || campaign.commercial_name || campaign.name)}</h1>
      <p className="mx-auto mt-3 max-w-2xl opacity-80">{String(visual.heroSubtitle || campaign.description || "Escolha sua oferta.")}</p>
      {campaign.ends_at && <p className="mt-4 flex items-center justify-center gap-2 text-sm opacity-70"><Clock size={15} /> Válido até {new Date(campaign.ends_at).toLocaleString("pt-BR")}</p>}
      <h2 className="mt-12 text-2xl font-bold">{String(visual.offersTitle || "Ofertas disponíveis")}</h2>
      <section ref={offersRef} id="strategic-offers" aria-label="Ofertas da campanha" className="mt-6 grid gap-4 md:grid-cols-2">
        {offers.map((offer, index) => { const product = offer.product_id ? products[offer.product_id] : null; return <article ref={index === 0 ? firstOfferRef : index === offers.length - 1 ? lastOfferRef : undefined} key={offer.id} className={`rounded-2xl border p-5 text-left ${offer.highlighted ? "border-2" : "border-white/15"}`} style={{ borderColor: offer.highlighted ? accent : undefined }}>
          {(offer.image_mobile_url || offer.image_desktop_url) && <img src={offer.image_mobile_url || offer.image_desktop_url || ""} alt="" className="mb-4 h-44 w-full rounded-xl object-cover" loading="lazy" onError={(event) => { event.currentTarget.hidden = true; }} />}
          <div className="flex items-start justify-between gap-3"><div><p className="text-lg font-bold">{offer.title}</p><p className="mt-1 text-sm opacity-75">{offer.description}</p></div>{offer.badge_text && <span className="rounded-full px-2 py-1 text-xs" style={{ background: accent, color: background }}>{offer.badge_text}</span>}</div>
          <div className="mt-5 flex items-center justify-between gap-3"><div><span className="text-2xl font-black" style={{ color: accent }}>R$ {offer.price_promotional.toFixed(2)}</span>{offer.price_original > offer.price_promotional && <span className="ml-2 text-sm line-through opacity-60">R$ {offer.price_original.toFixed(2)}</span>}</div><button onClick={() => { trackEvent("strategic_campaign_offer_click", undefined, { campaign_id: campaign.id, campaign_slug: campaign.slug, offer_id: offer.id }); if (product) { addToCart(product, 1, "M", [], [{ productId: product.id, name: product.name, price: product.price, icon: product.icon }], 1, offer.price_promotional, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, { campaignId: campaign.id, offerId: offer.id, campaignSlug: campaign.slug }); navigate("/cart"); } else if (offer.kit_id) navigate(`/combo/${encodeURIComponent(offer.kit_id)}?strategic_offer_id=${encodeURIComponent(offer.id)}`); }} disabled={!product && !offer.kit_id} className="rounded-lg px-4 py-2 text-sm font-bold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" style={{ background: accent, color: background }}>{offer.button_text || "Comprar"}</button></div>
        </article>; })}
      </section>
      {showScrollHint && <button type="button" onClick={scrollToOffers} aria-label="Rolar até as próximas ofertas" className="sticky bottom-5 mt-8 rounded-full p-3 shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" style={{ background: accent, color: background }}><ArrowDown aria-hidden="true" className="motion-safe:animate-bounce" /></button>}
      <p className="mt-12 text-center text-sm opacity-60">{String(visual.footerText || "")}</p>
    </section>
  </main>;
}
