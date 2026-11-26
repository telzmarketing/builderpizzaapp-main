import { useEffect, useMemo, useState } from "react";
import { Archive, ArrowDown, ArrowUp, Copy, Edit3, Loader2, PackagePlus, Plus, Save, Search, X } from "lucide-react";
import MediaUpload from "@/components/admin/MediaUpload";
import {
  campaignsApi,
  productsApi,
  strategicCampaignsApi,
  type ApiProduct,
  type ApiPromotionalKit,
  type ApiStrategicCampaign,
  type ApiStrategicOffer,
} from "@/lib/api";

type SourceType = "product" | "kit";

type OfferDraft = {
  code: string;
  title: string;
  description: string;
  sourceType: SourceType;
  sourceId: string;
  priceOriginal: string;
  pricePromotional: string;
  quantityLimit: string;
  maxPerCustomer: string;
  salesStartsAt: string;
  salesEndsAt: string;
  buttonText: string;
  badgeText: string;
  imageDesktopUrl: string;
  imageMobileUrl: string;
  highlighted: boolean;
  active: boolean;
};

const inputClass = "mt-1 w-full rounded-xl border border-surface-03 bg-surface-02 px-3 py-2.5 text-sm text-cream outline-none focus:border-gold";

function emptyDraft(campaign: ApiStrategicCampaign): OfferDraft {
  const next = campaign.offers.length + 1;
  return {
    code: `${campaign.slug.toUpperCase().replace(/-/g, "_")}-${String(next).padStart(3, "0")}`,
    title: "",
    description: "",
    sourceType: "product",
    sourceId: "",
    priceOriginal: "",
    pricePromotional: "",
    quantityLimit: "",
    maxPerCustomer: "",
    salesStartsAt: campaign.starts_at?.slice(0, 16) ?? "",
    salesEndsAt: campaign.ends_at?.slice(0, 16) ?? "",
    buttonText: "Comprar agora",
    badgeText: "",
    imageDesktopUrl: "",
    imageMobileUrl: "",
    highlighted: false,
    active: true,
  };
}

function offerDraft(offer: ApiStrategicOffer): OfferDraft {
  return {
    code: offer.code,
    title: offer.title,
    description: offer.description ?? "",
    sourceType: offer.kit_id ? "kit" : "product",
    sourceId: offer.kit_id ?? offer.product_id ?? "",
    priceOriginal: String(offer.price_original),
    pricePromotional: String(offer.price_promotional),
    quantityLimit: offer.quantity_limit == null ? "" : String(offer.quantity_limit),
    maxPerCustomer: offer.max_per_customer == null ? "" : String(offer.max_per_customer),
    salesStartsAt: offer.sales_starts_at?.slice(0, 16) ?? "",
    salesEndsAt: offer.sales_ends_at?.slice(0, 16) ?? "",
    buttonText: offer.button_text ?? "Comprar agora",
    badgeText: offer.badge_text ?? "",
    imageDesktopUrl: offer.image_desktop_url ?? "",
    imageMobileUrl: offer.image_mobile_url ?? "",
    highlighted: offer.highlighted,
    active: offer.active,
  };
}

function toIso(value: string) {
  return value ? new Date(value).toISOString() : null;
}

export default function StrategicCampaignOffersTab({
  campaign,
  onChanged,
}: {
  campaign: ApiStrategicCampaign;
  onChanged: (campaign: ApiStrategicCampaign) => void;
}) {
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [kits, setKits] = useState<ApiPromotionalKit[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<ApiStrategicOffer | null>(null);
  const [draft, setDraft] = useState<OfferDraft>(() => emptyDraft(campaign));
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setCatalogLoading(true);
    Promise.all([productsApi.list(true), campaignsApi.listKits(true)])
      .then(([productRows, kitRows]) => {
        setProducts(productRows);
        setKits(kitRows);
        setCatalogError("");
      })
      .catch((error) => setCatalogError(error instanceof Error ? error.message : "Não foi possível carregar o catálogo."))
      .finally(() => setCatalogLoading(false));
  }, []);

  useEffect(() => {
    if (!formOpen) setDraft(emptyDraft(campaign));
  }, [campaign, formOpen]);

  const sources = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    const rows = draft.sourceType === "product"
      ? products.map((item) => ({ id: item.id, name: item.name, price: item.price, detail: item.product_type || "Produto" }))
      : kits.map((item) => ({ id: item.id, name: item.name, price: item.price_promotional, detail: "Combo" }));
    return term ? rows.filter((item) => item.name.toLocaleLowerCase("pt-BR").includes(term)) : rows;
  }, [draft.sourceType, kits, products, search]);

  const openCreate = () => {
    setEditing(null);
    setDraft(emptyDraft(campaign));
    setSearch("");
    setMessage("");
    setFormOpen(true);
  };

  const openEdit = (offer: ApiStrategicOffer) => {
    setEditing(offer);
    setDraft(offerDraft(offer));
    setSearch("");
    setMessage("");
    setFormOpen(true);
  };

  const reloadCampaign = async () => onChanged(await strategicCampaignsApi.get(campaign.id));

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!draft.sourceId) {
      setMessage("Selecione um produto ou combo do catálogo.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const common = {
        title: draft.title.trim(),
        description: draft.description.trim() || null,
        price_original: Number(draft.priceOriginal),
        price_promotional: Number(draft.pricePromotional),
        quantity_limit: draft.quantityLimit ? Number(draft.quantityLimit) : null,
        max_per_customer: draft.maxPerCustomer ? Number(draft.maxPerCustomer) : null,
        sales_starts_at: toIso(draft.salesStartsAt),
        sales_ends_at: toIso(draft.salesEndsAt),
        show_when_sold_out: true,
        button_text: draft.buttonText.trim() || null,
        image_desktop_url: draft.imageDesktopUrl || null,
        image_mobile_url: draft.imageMobileUrl || null,
        badge_text: draft.badgeText.trim() || null,
        highlighted: draft.highlighted,
        display_order: editing?.display_order ?? campaign.offers.length,
      };
      if (editing) {
        await strategicCampaignsApi.updateOffer(editing.id, { ...common, active: draft.active });
      } else {
        await strategicCampaignsApi.addOffer(campaign.id, {
          ...common,
          code: draft.code.trim(),
          product_id: draft.sourceType === "product" ? draft.sourceId : null,
          kit_id: draft.sourceType === "kit" ? draft.sourceId : null,
        });
      }
      await reloadCampaign();
      setFormOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível salvar a oferta.");
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (offer: ApiStrategicOffer) => {
    setSaving(true);
    try {
      await strategicCampaignsApi.updateOffer(offer.id, { active: !offer.active });
      await reloadCampaign();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível alterar a oferta.");
    } finally {
      setSaving(false);
    }
  };

  const duplicate = async (offer: ApiStrategicOffer) => {
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.duplicateOffer(offer.id);
      await reloadCampaign();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível duplicar a oferta.");
    } finally {
      setSaving(false);
    }
  };

  const archive = async (offer: ApiStrategicOffer) => {
    if (!window.confirm(`Arquivar a oferta “${offer.title}”? O histórico comercial será preservado.`)) return;
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.archiveOffer(offer.id);
      await reloadCampaign();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível arquivar a oferta.");
    } finally {
      setSaving(false);
    }
  };

  const move = async (offerId: string, direction: -1 | 1) => {
    const ordered = [...campaign.offers].filter((item) => !item.archived_at).sort((a, b) => a.display_order - b.display_order);
    const index = ordered.findIndex((item) => item.id === offerId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    setSaving(true);
    setMessage("");
    try {
      await strategicCampaignsApi.reorderOffers(campaign.id, ordered.map((item) => item.id));
      await reloadCampaign();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível reordenar as ofertas.");
    } finally {
      setSaving(false);
    }
  };

  const discount = Number(draft.priceOriginal) > 0
    ? Math.max(0, Math.round((1 - Number(draft.pricePromotional || 0) / Number(draft.priceOriginal)) * 100))
    : 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-cream">Ofertas da campanha</h2>
          <p className="text-sm text-stone">Use produtos e combos existentes. Nenhum item é duplicado no catálogo.</p>
        </div>
        <button type="button" onClick={openCreate} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-bold text-cream">
          <Plus size={16} /> Adicionar oferta
        </button>
      </div>

      {message && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{message}</div>}

      {campaign.offers.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-surface-03 bg-surface-01 px-6 py-12 text-center">
          <PackagePlus className="mx-auto text-gold" size={34} />
          <h3 className="mt-3 font-bold text-cream">Nenhuma oferta cadastrada</h3>
          <p className="mt-1 text-sm text-stone">Cadastre a primeira oferta diretamente pela interface administrativa.</p>
          <button type="button" onClick={openCreate} className="mt-4 rounded-xl bg-gold px-4 py-2 text-sm font-bold text-cream">Adicionar oferta</button>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {[...campaign.offers].filter((offer) => !offer.archived_at).sort((a, b) => a.display_order - b.display_order).map((offer, index, ordered) => (
            <article key={offer.id} className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-01">
              {offer.image_desktop_url ? <img src={offer.image_desktop_url} alt="" className="h-40 w-full object-cover" /> : <div className="flex h-28 items-center justify-center bg-surface-02 text-sm text-stone">Sem imagem comercial</div>}
              <div className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="text-xs font-semibold uppercase tracking-wider text-gold">{offer.code}</p><h3 className="font-bold text-cream">{offer.title}</h3></div>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${offer.active ? "bg-emerald-500/15 text-emerald-300" : "bg-surface-03 text-stone"}`}>{offer.active ? "Ativa" : "Inativa"}</span>
                </div>
                <div className="flex items-baseline gap-2"><strong className="text-xl text-gold">R$ {offer.price_promotional.toFixed(2)}</strong>{offer.price_original > offer.price_promotional && <span className="text-sm text-stone line-through">R$ {offer.price_original.toFixed(2)}</span>}</div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => openEdit(offer)} className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment"><Edit3 size={14} /> Editar</button>
                  <button type="button" disabled={saving} onClick={() => void toggle(offer)} className="rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment">{offer.active ? "Desativar" : "Ativar"}</button>
                  <button type="button" disabled={saving} onClick={() => void duplicate(offer)} className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-semibold text-parchment"><Copy size={14} /> Duplicar</button>
                  <button type="button" disabled={saving || index === 0} onClick={() => void move(offer.id, -1)} aria-label="Mover oferta para cima" className="rounded-lg border border-surface-03 p-2 text-parchment disabled:opacity-30"><ArrowUp size={14} /></button>
                  <button type="button" disabled={saving || index === ordered.length - 1} onClick={() => void move(offer.id, 1)} aria-label="Mover oferta para baixo" className="rounded-lg border border-surface-03 p-2 text-parchment disabled:opacity-30"><ArrowDown size={14} /></button>
                  <button type="button" disabled={saving} onClick={() => void archive(offer)} className="inline-flex items-center gap-2 rounded-lg border border-red-500/30 px-3 py-2 text-sm font-semibold text-red-300"><Archive size={14} /> Arquivar</button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-5" onMouseDown={(event) => { if (event.target === event.currentTarget) setFormOpen(false); }}>
          <form onSubmit={save} className="max-h-[95vh] w-full max-w-5xl overflow-y-auto rounded-t-2xl border border-surface-03 bg-surface-00 p-5 shadow-2xl sm:rounded-2xl">
            <div className="flex items-start justify-between gap-3">
              <div><h2 className="text-xl font-bold text-cream">{editing ? "Editar oferta" : "Adicionar oferta"}</h2><p className="text-sm text-stone">Configuração comercial e apresentação visual individual.</p></div>
              <button type="button" onClick={() => setFormOpen(false)} className="rounded-lg p-2 text-stone hover:bg-surface-02 hover:text-cream" aria-label="Fechar"><X /></button>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
              <div className="space-y-5">
                <section className="space-y-4 rounded-2xl border border-surface-03 bg-surface-01 p-4">
                  <h3 className="font-bold text-cream">Referência do catálogo</h3>
                  <div className="grid grid-cols-2 gap-2">
                    {(["product", "kit"] as SourceType[]).map((type) => <button key={type} type="button" disabled={Boolean(editing)} onClick={() => setDraft((current) => ({ ...current, sourceType: type, sourceId: "" }))} className={`rounded-xl border px-3 py-2 text-sm font-semibold ${draft.sourceType === type ? "border-gold bg-gold/15 text-gold" : "border-surface-03 text-parchment"}`}>{type === "product" ? "Produto" : "Combo"}</button>)}
                  </div>
                  <label className="block text-xs font-medium text-parchment">Pesquisar no catálogo<div className="relative"><Search className="absolute left-3 top-3.5 text-stone" size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} className={`${inputClass} pl-9`} placeholder="Nome do produto ou combo" /></div></label>
                  {catalogLoading ? <Loader2 className="animate-spin text-gold" /> : catalogError ? <p className="text-sm text-red-300">{catalogError}</p> : <div className="max-h-56 space-y-2 overflow-y-auto">{sources.map((source) => <button key={source.id} type="button" disabled={Boolean(editing)} onClick={() => setDraft((current) => ({ ...current, sourceId: source.id, title: current.title || source.name, priceOriginal: current.priceOriginal || String(source.price), pricePromotional: current.pricePromotional || String(source.price) }))} className={`flex w-full items-center justify-between rounded-xl border p-3 text-left ${draft.sourceId === source.id ? "border-gold bg-gold/10" : "border-surface-03 bg-surface-02"}`}><span><strong className="block text-sm text-cream">{source.name}</strong><small className="text-stone">{source.detail}</small></span><span className="text-sm font-semibold text-gold">R$ {Number(source.price).toFixed(2)}</span></button>)}</div>}
                </section>

                <section className="grid gap-4 rounded-2xl border border-surface-03 bg-surface-01 p-4 sm:grid-cols-2">
                  <h3 className="sm:col-span-2 font-bold text-cream">Condições comerciais</h3>
                  <label className="text-xs text-parchment">Código exclusivo<input required disabled={Boolean(editing)} value={draft.code} onChange={(event) => setDraft({ ...draft, code: event.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-parchment">Título comercial<input required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-parchment sm:col-span-2">Descrição<textarea value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} className={`${inputClass} min-h-20`} /></label>
                  <label className="text-xs text-parchment">Preço original<input required min="0" step="0.01" type="number" value={draft.priceOriginal} onChange={(event) => setDraft({ ...draft, priceOriginal: event.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-parchment">Preço promocional<input required min="0" step="0.01" type="number" value={draft.pricePromotional} onChange={(event) => setDraft({ ...draft, pricePromotional: event.target.value })} className={inputClass} /><span className="mt-1 block text-gold">Desconto calculado: {discount}%</span></label>
                  <label className="text-xs text-parchment">Quantidade máxima<input min="0" type="number" value={draft.quantityLimit} onChange={(event) => setDraft({ ...draft, quantityLimit: event.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-parchment">Limite por cliente<input min="1" type="number" value={draft.maxPerCustomer} onChange={(event) => setDraft({ ...draft, maxPerCustomer: event.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-parchment">Início da oferta<input type="datetime-local" value={draft.salesStartsAt} onChange={(event) => setDraft({ ...draft, salesStartsAt: event.target.value })} className={inputClass} /></label>
                  <label className="text-xs text-parchment">Encerramento da oferta<input type="datetime-local" value={draft.salesEndsAt} onChange={(event) => setDraft({ ...draft, salesEndsAt: event.target.value })} className={inputClass} /></label>
                </section>
              </div>

              <section className="space-y-5 rounded-2xl border border-surface-03 bg-surface-01 p-4">
                <h3 className="font-bold text-cream">Apresentação visual</h3>
                <MediaUpload mediaType="image" label="Imagem desktop" value={draft.imageDesktopUrl} onChange={(value) => setDraft((current) => ({ ...current, imageDesktopUrl: value }))} sizeGuide="Recomendado: 1200 × 800 px, WebP/JPG/PNG." />
                <MediaUpload mediaType="image" label="Imagem smartphone" value={draft.imageMobileUrl} onChange={(value) => setDraft((current) => ({ ...current, imageMobileUrl: value }))} sizeGuide="Recomendado: 800 × 800 px, WebP/JPG/PNG." />
                <label className="block text-xs text-parchment">Texto do botão<input value={draft.buttonText} onChange={(event) => setDraft({ ...draft, buttonText: event.target.value })} className={inputClass} /></label>
                <label className="block text-xs text-parchment">Selo promocional<input value={draft.badgeText} onChange={(event) => setDraft({ ...draft, badgeText: event.target.value })} className={inputClass} placeholder="Ex.: Mais vendida" /></label>
                <label className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3 text-sm text-parchment"><input type="checkbox" checked={draft.highlighted} onChange={(event) => setDraft({ ...draft, highlighted: event.target.checked })} className="accent-gold" /> Destacar visualmente esta oferta</label>
                {editing && <label className="flex items-center gap-3 rounded-xl border border-surface-03 bg-surface-02 p-3 text-sm text-parchment"><input type="checkbox" checked={draft.active} onChange={(event) => setDraft({ ...draft, active: event.target.checked })} className="accent-gold" /> Oferta ativa</label>}
              </section>
            </div>

            <div className="mt-6 flex flex-col-reverse gap-2 border-t border-surface-03 pt-4 sm:flex-row sm:justify-end">
              <button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border border-surface-03 px-4 py-2.5 text-sm font-semibold text-parchment">Cancelar</button>
              <button disabled={saving || catalogLoading} className="inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-bold text-cream disabled:opacity-60">{saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Salvar oferta</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
