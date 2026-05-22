import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowDown, ArrowLeft, ArrowUp, Eye, Image, Loader2, Save, Send, Video } from "lucide-react";
import MediaUpload from "@/components/admin/MediaUpload";
import {
  productsApi,
  productPromotionsApi,
  promotionLandingsApi,
  type ApiProduct,
  type ApiProductPromotion,
  type ApiPromotionLandingAlignment,
  type ApiPromotionLandingImagePosition,
  type ApiPromotionLandingMediaSlot,
  type ApiPromotionLandingOverlay,
  type ApiPromotionLandingPage,
  type ApiPromotionLandingStatus,
} from "@/lib/api";

type FormState = {
  title: string;
  subtitle: string;
  description: string;
  cta_text: string;
  image_url: string;
  image_url_2: string;
  video_url: string;
  media_order: ApiPromotionLandingMediaSlot[];
  image_position: ApiPromotionLandingImagePosition;
  content_alignment: ApiPromotionLandingAlignment;
  overlay_style: ApiPromotionLandingOverlay;
  badge_text: string;
  free_shipping_label: string;
  gift_label_prefix: string;
  gift_fallback_label: string;
  active_offer_label: string;
  slug: string;
  status: ApiPromotionLandingStatus;
  is_active: boolean;
};

const DEFAULT_MEDIA_ORDER: ApiPromotionLandingMediaSlot[] = ["image_url", "image_url_2", "video_url"];
const FREE_SHIPPING_LABEL = "Frete Grátis na Promoção";
const MEDIA_SLOT_CONFIG: Record<ApiPromotionLandingMediaSlot, {
  label: string;
  mediaType: "image" | "video";
  hint: string;
  sizeGuide: string;
}> = {
  image_url: {
    label: "Imagem principal",
    mediaType: "image",
    hint: "Imagem promocional usada no carrossel da landing.",
    sizeGuide: "Recomendado: 1080x1350 ou 1200x1200",
  },
  image_url_2: {
    label: "Segunda imagem",
    mediaType: "image",
    hint: "Imagem complementar da landing promocional.",
    sizeGuide: "Recomendado: 1080x1350 ou 1200x1200",
  },
  video_url: {
    label: "Video curto",
    mediaType: "video",
    hint: "O carrossel exibe o video por ate 15 segundos e passa para a proxima midia.",
    sizeGuide: "Recomendado: MP4/WebM vertical, ate 15 segundos",
  },
};

const normalizeMediaOrder = (order?: ApiPromotionLandingMediaSlot[] | null) => {
  const unique = (order || []).filter((slot, index, all) =>
    DEFAULT_MEDIA_ORDER.includes(slot) && all.indexOf(slot) === index
  );
  return [...unique, ...DEFAULT_MEDIA_ORDER.filter((slot) => !unique.includes(slot))];
};

const normalizeFreeShippingLabel = (value?: string | null) => {
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

const emptyForm = (productName = ""): FormState => ({
  title: productName ? `${productName} em promocao` : "",
  subtitle: "Oferta especial por tempo limitado",
  description: "",
  cta_text: "Quero essa pizza",
  image_url: "",
  image_url_2: "",
  video_url: "",
  media_order: DEFAULT_MEDIA_ORDER,
  image_position: "center",
  content_alignment: "center",
  overlay_style: "dark-gradient",
  badge_text: "Oferta do dia",
  free_shipping_label: FREE_SHIPPING_LABEL,
  gift_label_prefix: "Brinde",
  gift_fallback_label: "Brinde incluído",
  active_offer_label: "Oferta ativa agora",
  slug: "",
  status: "draft",
  is_active: true,
});

const inputClass = "w-full rounded-lg border border-surface-03 bg-surface-03 px-3 py-2 text-sm text-cream outline-none transition-colors placeholder:text-stone/60 focus:border-gold";
const labelClass = "mb-1 block text-xs font-semibold text-parchment";

export default function PromotionalLandingEditor() {
  const { productId: routeProductId, promotionId: routePromotionId } = useParams<{ productId: string; promotionId: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<ApiProduct | null>(null);
  const [promotion, setPromotion] = useState<ApiProductPromotion | null>(null);
  const [landing, setLanding] = useState<ApiPromotionLandingPage | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const pathLandingIds = useMemo(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    const landingIndex = parts.lastIndexOf("landing");
    if (landingIndex < 0) return { productId: routeProductId, promotionId: routePromotionId };
    return {
      productId: parts[landingIndex + 1] || routeProductId,
      promotionId: parts[landingIndex + 2] || routePromotionId,
    };
  }, [routeProductId, routePromotionId]);

  const productId = routeProductId?.startsWith("prod-") ? routeProductId : pathLandingIds.productId;
  const promotionId = routePromotionId?.startsWith("pp-") ? routePromotionId : pathLandingIds.promotionId;

  useEffect(() => {
    if (!productId || !promotionId) return;
    setLoading(true);
    setError("");
    Promise.allSettled([
      productsApi.get(productId),
      productPromotionsApi.list(productId),
      promotionLandingsApi.getByProductPromotion(productId, promotionId),
    ])
      .then(([prodResult, promotionsResult, existingResult]) => {
        if (prodResult.status !== "fulfilled") {
          throw prodResult.reason;
        }
        if (promotionsResult.status !== "fulfilled") {
          throw promotionsResult.reason;
        }
        const prod = prodResult.value;
        const promotions = promotionsResult.value;
        const existing = existingResult.status === "fulfilled" ? existingResult.value : null;
        const promo = promotions.find((item) => item.id === promotionId) ?? null;
        setProduct(prod);
        setPromotion(promo);
        setLanding(existing);
        if (existing) {
          setForm({
            title: existing.title,
            subtitle: existing.subtitle ?? "",
            description: existing.description ?? "",
            cta_text: existing.cta_text || "Quero essa pizza",
            image_url: existing.image_url ?? "",
            image_url_2: existing.image_url_2 ?? "",
            video_url: existing.video_url ?? "",
            media_order: normalizeMediaOrder(existing.media_order),
            image_position: existing.image_position,
            content_alignment: existing.content_alignment,
            overlay_style: existing.overlay_style,
            badge_text: existing.badge_text ?? "",
            free_shipping_label: normalizeFreeShippingLabel(existing.free_shipping_label),
            gift_label_prefix: existing.gift_label_prefix || "Brinde",
            gift_fallback_label: existing.gift_fallback_label || "Brinde incluído",
            active_offer_label: existing.active_offer_label || "Oferta ativa agora",
            slug: existing.slug,
            status: existing.status,
            is_active: existing.is_active,
          });
        } else {
          setForm(emptyForm(prod.name));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar a landing."))
      .finally(() => setLoading(false));
  }, [productId, promotionId]);

  const validity = useMemo(() => {
    if (!promotion) return "";
    const days = promotion.valid_weekdays.join(", ");
    const hours = [promotion.start_time, promotion.end_time].filter(Boolean).join(" - ");
    const dates = [promotion.start_date, promotion.end_date].filter(Boolean).join(" ate ");
    return [days ? `Dias: ${days}` : "", hours ? `Horario: ${hours}` : "", dates ? `Validade: ${dates}` : ""].filter(Boolean).join(" | ");
  }, [promotion]);

  const payload = (status: ApiPromotionLandingStatus) => ({
    product_id: productId!,
    promotion_id: promotionId!,
    title: form.title.trim(),
    subtitle: form.subtitle.trim() || null,
    description: form.description.trim() || null,
    cta_text: form.cta_text.trim() || "Quero essa pizza",
    image_url: form.image_url || null,
    image_url_2: form.image_url_2 || null,
    video_url: form.video_url || null,
    media_order: normalizeMediaOrder(form.media_order),
    image_position: form.image_position,
    content_alignment: form.content_alignment,
    overlay_style: form.overlay_style,
    badge_text: form.badge_text.trim() || null,
    free_shipping_label: normalizeFreeShippingLabel(form.free_shipping_label),
    gift_label_prefix: form.gift_label_prefix.trim() || "Brinde",
    gift_fallback_label: form.gift_fallback_label.trim() || "Brinde incluído",
    active_offer_label: form.active_offer_label.trim() || "Oferta ativa agora",
    slug: form.slug.trim() || null,
    status,
    is_active: form.is_active,
  });

  const save = async (status: ApiPromotionLandingStatus) => {
    if (!productId || !promotionId || !form.title.trim()) return;
    setSaving(true);
    setError("");
    try {
      const data = payload(status);
      const saved = landing
        ? await promotionLandingsApi.update(landing.id, data)
        : await promotionLandingsApi.create(data);
      setLanding(saved);
      setForm((current) => ({ ...current, slug: saved.slug, status: saved.status }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar landing.");
    } finally {
      setSaving(false);
    }
  };

  const moveMediaSlot = (slot: ApiPromotionLandingMediaSlot, direction: -1 | 1) => {
    setForm((current) => {
      const mediaOrder = normalizeMediaOrder(current.media_order);
      const index = mediaOrder.indexOf(slot);
      const targetIndex = index + direction;
      if (index < 0 || targetIndex < 0 || targetIndex >= mediaOrder.length) return current;
      const nextOrder = [...mediaOrder];
      [nextOrder[index], nextOrder[targetIndex]] = [nextOrder[targetIndex], nextOrder[index]];
      return { ...current, media_order: nextOrder };
    });
  };

  const setMediaSlotValue = (slot: ApiPromotionLandingMediaSlot, value: string) => {
    setForm((current) => ({ ...current, [slot]: value }));
  };

  const preview = () => {
    const slug = landing?.slug || form.slug;
    if (slug) window.open(`/promocao/${slug}`, "_blank", "noopener,noreferrer");
  };

  if (loading) {
    return (
      <div className="flex min-h-[360px] items-center justify-center gap-2 text-stone">
        <Loader2 size={18} className="animate-spin" />
        Carregando landing...
      </div>
    );
  }

  if (!product || !promotion) {
    return (
      <div className="rounded-lg border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-200">
        Produto ou promocao nao encontrados.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => navigate("/painel/products")}
          className="inline-flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-03 px-3 py-2 text-sm font-semibold text-parchment transition-colors hover:text-cream"
        >
          <ArrowLeft size={16} />
          Voltar
        </button>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={preview}
            disabled={!landing?.slug}
            className="inline-flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-03 px-3 py-2 text-sm font-semibold text-parchment transition-colors hover:text-cream disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Eye size={16} />
            Visualizar
          </button>
          <button
            onClick={() => save("draft")}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-03 px-3 py-2 text-sm font-semibold text-parchment transition-colors hover:text-cream disabled:opacity-60"
          >
            <Save size={16} />
            Salvar rascunho
          </button>
          <button
            onClick={() => save("published")}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-gold px-4 py-2 text-sm font-bold text-cream transition-colors hover:bg-gold/90 disabled:opacity-60"
          >
            <Send size={16} />
            Publicar
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="space-y-5">
          <div className="rounded-lg border border-surface-03 bg-surface-02 p-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className={labelClass}>Produto vinculado</label>
                <input value={product.name} readOnly className={`${inputClass} opacity-80`} />
              </div>
              <div>
                <label className={labelClass}>Promocao vinculada</label>
                <input value={promotion.name} readOnly className={`${inputClass} opacity-80`} />
              </div>
            </div>
            {validity && <p className="mt-3 text-xs text-stone">{validity}</p>}
          </div>

          <div className="rounded-lg border border-surface-03 bg-surface-02 p-4 space-y-4">
            <div className="grid gap-3 md:grid-cols-[160px,1fr]">
              <div>
                <label className={labelClass}>Status</label>
                <select value={form.status} onChange={(e) => setForm((current) => ({ ...current, status: e.target.value as ApiPromotionLandingStatus }))} className={inputClass}>
                  <option value="draft">Rascunho</option>
                  <option value="published">Publicada</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Slug</label>
                <input value={form.slug} onChange={(e) => setForm((current) => ({ ...current, slug: e.target.value }))} className={inputClass} placeholder="pizza-calabresa" />
              </div>
            </div>

            <div>
              <label className={labelClass}>Titulo principal</label>
              <input value={form.title} onChange={(e) => setForm((current) => ({ ...current, title: e.target.value }))} className={inputClass} maxLength={220} />
            </div>

            <div>
              <label className={labelClass}>Texto principal</label>
              <input value={form.subtitle} onChange={(e) => setForm((current) => ({ ...current, subtitle: e.target.value }))} className={inputClass} maxLength={500} />
            </div>

            <div>
              <label className={labelClass}>Texto auxiliar</label>
              <textarea value={form.description} onChange={(e) => setForm((current) => ({ ...current, description: e.target.value }))} className={`${inputClass} min-h-24 resize-none`} />
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className={labelClass}>Texto do CTA</label>
                <input value={form.cta_text} onChange={(e) => setForm((current) => ({ ...current, cta_text: e.target.value }))} className={inputClass} maxLength={80} />
              </div>
              <div>
                <label className={labelClass}>Badge</label>
                <input value={form.badge_text} onChange={(e) => setForm((current) => ({ ...current, badge_text: e.target.value }))} className={inputClass} maxLength={80} />
              </div>
            </div>

            <div className="rounded-lg border border-surface-03 bg-surface-01 p-3">
              <p className="text-sm font-bold text-cream">Textos dos beneficios</p>
              <p className="mb-3 text-xs text-stone">Esses textos aparecem nos selos abaixo do titulo da landing.</p>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className={labelClass}>Texto do frete gratis</label>
                  <input value={form.free_shipping_label} onChange={(e) => setForm((current) => ({ ...current, free_shipping_label: e.target.value }))} className={inputClass} maxLength={160} />
                </div>
                <div>
                  <label className={labelClass}>Texto da oferta ativa</label>
                  <input value={form.active_offer_label} onChange={(e) => setForm((current) => ({ ...current, active_offer_label: e.target.value }))} className={inputClass} maxLength={160} />
                </div>
                <div>
                  <label className={labelClass}>Prefixo do brinde</label>
                  <input value={form.gift_label_prefix} onChange={(e) => setForm((current) => ({ ...current, gift_label_prefix: e.target.value }))} className={inputClass} maxLength={80} />
                </div>
                <div>
                  <label className={labelClass}>Texto do brinde sem nome</label>
                  <input value={form.gift_fallback_label} onChange={(e) => setForm((current) => ({ ...current, gift_fallback_label: e.target.value }))} className={inputClass} maxLength={160} />
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-surface-03 bg-surface-02 p-4 space-y-4">
            <div className="rounded-lg border border-surface-03 bg-surface-01 p-3">
              <p className="text-sm font-bold text-cream">Ordem do carrossel</p>
              <p className="mb-3 text-xs text-stone">Use as setas para definir a ordem em que imagens e video aparecem na landing.</p>
              <div className="space-y-2">
                {normalizeMediaOrder(form.media_order).map((slot, index, order) => {
                  const config = MEDIA_SLOT_CONFIG[slot];
                  const SlotIcon = config.mediaType === "video" ? Video : Image;
                  return (
                    <div key={slot} className="flex items-center justify-between gap-3 rounded-lg border border-surface-03 bg-surface-02 px-3 py-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gold/15 text-gold">
                          <SlotIcon size={16} />
                        </span>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-cream">{index + 1}. {config.label}</p>
                          <p className="text-xs text-stone">Posicao {index + 1} no carrossel</p>
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <button
                          type="button"
                          onClick={() => moveMediaSlot(slot, -1)}
                          disabled={index === 0}
                          className="flex h-8 w-8 items-center justify-center rounded-lg border border-surface-03 bg-surface-03 text-parchment transition-colors hover:text-gold disabled:cursor-not-allowed disabled:opacity-40"
                          title="Subir midia"
                        >
                          <ArrowUp size={15} />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveMediaSlot(slot, 1)}
                          disabled={index === order.length - 1}
                          className="flex h-8 w-8 items-center justify-center rounded-lg border border-surface-03 bg-surface-03 text-parchment transition-colors hover:text-gold disabled:cursor-not-allowed disabled:opacity-40"
                          title="Descer midia"
                        >
                          <ArrowDown size={15} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <MediaUpload
              value={form.image_url}
              onChange={(value) => setForm((current) => ({ ...current, image_url: value }))}
              mediaType="image"
              label="Imagem principal"
              hint="Primeira mídia exibida no carrossel da landing."
              sizeGuide="Recomendado: 1080x1350 ou 1200x1200"
              maxKBImage={3000}
            />
            <MediaUpload
              value={form.image_url_2}
              onChange={(value) => setForm((current) => ({ ...current, image_url_2: value }))}
              mediaType="image"
              label="Segunda imagem"
              hint="Aparece como segunda lâmina do carrossel."
              sizeGuide="Recomendado: 1080x1350 ou 1200x1200"
              maxKBImage={3000}
            />
            <MediaUpload
              value={form.video_url}
              onChange={(value) => setForm((current) => ({ ...current, video_url: value }))}
              mediaType="video"
              label="Vídeo curto"
              hint="O carrossel exibe o vídeo por até 15 segundos e passa para a próxima mídia."
              sizeGuide="Recomendado: MP4/WebM vertical, até 15 segundos"
              maxKBVideo={50000}
            />

            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <label className={labelClass}>Posicao da imagem</label>
                <select value={form.image_position} onChange={(e) => setForm((current) => ({ ...current, image_position: e.target.value as ApiPromotionLandingImagePosition }))} className={inputClass}>
                  <option value="center">Centro</option>
                  <option value="top">Topo</option>
                  <option value="bottom">Base</option>
                  <option value="left">Esquerda</option>
                  <option value="right">Direita</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Alinhamento</label>
                <select value={form.content_alignment} onChange={(e) => setForm((current) => ({ ...current, content_alignment: e.target.value as ApiPromotionLandingAlignment }))} className={inputClass}>
                  <option value="left">Esquerda</option>
                  <option value="center">Centro</option>
                  <option value="right">Direita</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Overlay</label>
                <select value={form.overlay_style} onChange={(e) => setForm((current) => ({ ...current, overlay_style: e.target.value as ApiPromotionLandingOverlay }))} className={inputClass}>
                  <option value="dark-gradient">Escuro degradê</option>
                  <option value="dark">Escuro</option>
                  <option value="light">Claro</option>
                  <option value="brand">Marca</option>
                </select>
              </div>
            </div>
          </div>
        </section>

        <aside className="rounded-lg border border-surface-03 bg-surface-02 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <span className="text-sm font-bold text-cream">Resumo</span>
            <span className={`rounded-full px-2 py-1 text-xs font-semibold ${form.status === "published" ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"}`}>
              {form.status === "published" ? "Publicada" : "Rascunho"}
            </span>
          </div>
          <div className="space-y-3 text-sm text-stone">
            <p><span className="text-parchment">URL:</span> /promocao/{landing?.slug || form.slug || "slug-automatico"}</p>
            <p><span className="text-parchment">Promocao ativa agora:</span> {landing?.promotion_active_now ? "sim" : "nao"}</p>
            <p><span className="text-parchment">Catalogo:</span> so redireciona quando estiver publicada e a promocao estiver valida agora.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
