import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Eye, Loader2, Save, Send } from "lucide-react";
import ImageUpload from "@/components/admin/ImageUpload";
import {
  productsApi,
  productPromotionsApi,
  promotionLandingsApi,
  type ApiProduct,
  type ApiProductPromotion,
  type ApiPromotionLandingAlignment,
  type ApiPromotionLandingImagePosition,
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
  image_position: ApiPromotionLandingImagePosition;
  content_alignment: ApiPromotionLandingAlignment;
  overlay_style: ApiPromotionLandingOverlay;
  badge_text: string;
  slug: string;
  status: ApiPromotionLandingStatus;
  is_active: boolean;
};

const emptyForm = (productName = ""): FormState => ({
  title: productName ? `${productName} em promocao` : "",
  subtitle: "Oferta especial por tempo limitado",
  description: "",
  cta_text: "Quero essa pizza",
  image_url: "",
  image_position: "center",
  content_alignment: "center",
  overlay_style: "dark-gradient",
  badge_text: "Oferta do dia",
  slug: "",
  status: "draft",
  is_active: true,
});

const inputClass = "w-full rounded-lg border border-surface-03 bg-surface-03 px-3 py-2 text-sm text-cream outline-none transition-colors placeholder:text-stone/60 focus:border-gold";
const labelClass = "mb-1 block text-xs font-semibold text-parchment";

export default function PromotionalLandingEditor() {
  const { productId, promotionId } = useParams<{ productId: string; promotionId: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<ApiProduct | null>(null);
  const [promotion, setPromotion] = useState<ApiProductPromotion | null>(null);
  const [landing, setLanding] = useState<ApiPromotionLandingPage | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!productId || !promotionId) return;
    setLoading(true);
    setError("");
    Promise.all([
      productsApi.get(productId),
      productPromotionsApi.list(productId),
      promotionLandingsApi.getByProductPromotion(productId, promotionId),
    ])
      .then(([prod, promotions, existing]) => {
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
            image_position: existing.image_position,
            content_alignment: existing.content_alignment,
            overlay_style: existing.overlay_style,
            badge_text: existing.badge_text ?? "",
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
    image_position: form.image_position,
    content_alignment: form.content_alignment,
    overlay_style: form.overlay_style,
    badge_text: form.badge_text.trim() || null,
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
          </div>

          <div className="rounded-lg border border-surface-03 bg-surface-02 p-4 space-y-4">
            <ImageUpload
              value={form.image_url}
              onChange={(value) => setForm((current) => ({ ...current, image_url: value }))}
              label="Imagem principal"
              hint="Imagem vertical ou quadrada funciona melhor no mobile."
              sizeGuide="Recomendado: 1080x1350 ou 1200x1200"
              maxKB={1500}
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
