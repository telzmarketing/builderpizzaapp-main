import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Eye, Loader2, Plus, Save, Send } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { strategicCampaignsApi, type ApiStrategicCampaign, type ApiStrategicOffer, type StrategicCommercialConfig, type StrategicMarketingConfig, type StrategicCampaignMetrics } from "@/lib/api";

type VisualConfig = {
  backgroundColor?: string;
  textColor?: string;
  accentColor?: string;
  headerText?: string;
  heroTitle?: string;
  heroSubtitle?: string;
  heroImageUrl?: string;
  heroVideoUrl?: string;
  offersTitle?: string;
  footerText?: string;
};

const emptyVisual: VisualConfig = {
  backgroundColor: "#17120f", textColor: "#fff7ed", accentColor: "#d9a441",
  headerText: "Oferta especial", heroTitle: "Escolha sua oferta", heroSubtitle: "Condições exclusivas por tempo limitado.",
  heroImageUrl: "", heroVideoUrl: "", offersTitle: "Ofertas disponíveis", footerText: "Obrigado por comprar conosco.",
};

const emptyCommercial: StrategicCommercialConfig = {
  sales_mode: "immediate", allow_when_store_closed: false, require_scheduled_order: false,
  min_lead_minutes: 0, max_lead_days: null, allowed_payment_methods: [],
};
const emptyMarketing: StrategicMarketingConfig = { planned_budget: null, traffic_campaign_id: null, attribution_window_days: 30 };

export default function StrategicCampaigns() {
  const [campaigns, setCampaigns] = useState<ApiStrategicCampaign[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [visual, setVisual] = useState<VisualConfig>(emptyVisual);
  const [commercial, setCommercial] = useState<StrategicCommercialConfig>(emptyCommercial);
  const [marketing, setMarketing] = useState<StrategicMarketingConfig>(emptyMarketing);
  const [metrics, setMetrics] = useState<StrategicCampaignMetrics | null>(null);
  const [newCampaign, setNewCampaign] = useState({ name: "", commercial_name: "", slug: "", description: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const selected = useMemo(() => campaigns.find((item) => item.id === selectedId) ?? null, [campaigns, selectedId]);

  const load = async () => {
    setLoading(true);
    try {
      const data = await strategicCampaignsApi.list();
      setCampaigns(data);
      if (!selectedId && data[0]) setSelectedId(data[0].id);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Não foi possível carregar as campanhas."); }
    finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    setVisual({ ...emptyVisual, ...(selected?.visual_config as VisualConfig | undefined) });
    setCommercial({ ...emptyCommercial, ...(selected?.commercial_config ?? {}) });
    setMarketing({ ...emptyMarketing, ...(selected?.marketing_config ?? {}) });
    setMetrics(null);
    if (selected) void strategicCampaignsApi.metrics(selected.id).then(setMetrics).catch(() => setMetrics(null));
  }, [selected]);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const campaign = await strategicCampaignsApi.create({ ...newCampaign, starts_at: null, ends_at: null });
      setCampaigns((current) => [campaign, ...current]); setSelectedId(campaign.id); setNewCampaign({ name: "", commercial_name: "", slug: "", description: "" }); setMessage("Campanha criada.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Não foi possível criar a campanha."); }
    finally { setSaving(false); }
  };

  const saveVisual = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const updated = await strategicCampaignsApi.update(selected.id, { visual_config: visual, commercial_config: commercial, marketing_config: marketing });
      setCampaigns((current) => current.map((item) => item.id === updated.id ? updated : item)); setMessage("Editor salvo no rascunho.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Não foi possível salvar o editor."); }
    finally { setSaving(false); }
  };

  const publish = async () => {
    if (!selected) return;
    setSaving(true);
    try { await strategicCampaignsApi.publish(selected.id); await load(); setMessage("Campanha publicada."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Não foi possível publicar."); }
    finally { setSaving(false); }
  };

  const field = (key: keyof VisualConfig, label: string) => (
    <label className="block text-xs text-parchment">
      {label}
      <input value={visual[key] ?? ""} onChange={(event) => setVisual((current) => ({ ...current, [key]: event.target.value }))} className="mt-1 w-full rounded-lg border border-surface-03 bg-surface-03 px-3 py-2 text-sm text-cream" />
    </label>
  );

  return <div className="flex min-h-screen flex-col bg-surface-00 md:flex-row">
    <AdminSidebar />
    <main className="flex-1 space-y-6 overflow-y-auto p-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><p className="text-xs uppercase tracking-widest text-gold">Marketing</p><h1 className="text-2xl font-bold text-cream">Campanhas Estratégicas</h1><p className="text-sm text-stone">Editor de ofertas e publicação versionada.</p></div><AdminTopActions /></div>
      {message && <div className="rounded-lg border border-gold/30 bg-gold/10 p-3 text-sm text-gold">{message}</div>}
      <section className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <div className="space-y-4 rounded-2xl border border-surface-03 bg-surface-01 p-4">
          <form onSubmit={create} className="space-y-2"><h2 className="font-semibold text-cream">Nova campanha</h2><input required placeholder="Nome administrativo" value={newCampaign.name} onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })} className="w-full rounded-lg bg-surface-03 px-3 py-2 text-sm text-cream" /><input required placeholder="Slug" value={newCampaign.slug} onChange={(e) => setNewCampaign({ ...newCampaign, slug: e.target.value })} className="w-full rounded-lg bg-surface-03 px-3 py-2 text-sm text-cream" /><button disabled={saving} className="flex w-full items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-bold text-cream"><Plus size={16} /> Criar</button></form>
          <div className="border-t border-surface-03 pt-3">{loading ? <Loader2 className="mx-auto animate-spin text-gold" /> : campaigns.map((campaign) => <button key={campaign.id} onClick={() => setSelectedId(campaign.id)} className={`mb-2 w-full rounded-lg p-3 text-left ${campaign.id === selectedId ? "bg-gold/20 text-gold" : "bg-surface-02 text-parchment"}`}><span className="block font-semibold">{campaign.name}</span><span className="text-xs opacity-70">{campaign.status} · {campaign.offers.length} ofertas</span></button>)}</div>
        </div>
        {selected ? <div className="space-y-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold text-cream">{selected.name}</h2><p className="text-sm text-stone">/{selected.slug}</p></div><div className="flex gap-2"><a href={`/campanha-estrategica/${selected.slug}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm text-parchment"><Eye size={16} /> Preview público</a><button onClick={() => void publish()} disabled={saving || selected.offers.length === 0} className="flex items-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-bold text-cream"><Send size={16} /> Publicar</button></div></div>
          <div className="grid gap-6 lg:grid-cols-2"><div className="space-y-3 rounded-2xl border border-surface-03 bg-surface-01 p-4"><h3 className="font-semibold text-cream">Editor visual</h3>{field("headerText", "Texto do header")}{field("heroTitle", "Título principal")}{field("heroSubtitle", "Subtítulo")}{field("heroImageUrl", "Imagem do hero")}{field("heroVideoUrl", "Vídeo do hero")}{field("offersTitle", "Título das ofertas")}{field("footerText", "Rodapé")}<div className="grid grid-cols-3 gap-2">{field("backgroundColor", "Fundo")}{field("textColor", "Texto")}{field("accentColor", "Destaque")}</div><button onClick={() => void saveVisual()} disabled={saving} className="flex w-full items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-bold text-cream"><Save size={16} /> Salvar rascunho</button></div><div className="overflow-hidden rounded-2xl border border-surface-03" style={{ background: visual.backgroundColor, color: visual.textColor }}><div className="p-4 text-center text-sm" style={{ color: visual.accentColor }}>{visual.headerText}</div>{visual.heroImageUrl && <img src={visual.heroImageUrl} alt="" className="h-40 w-full object-cover" />}<div className="space-y-2 p-6 text-center"><h3 className="text-2xl font-bold">{visual.heroTitle}</h3><p>{visual.heroSubtitle}</p><h4 className="pt-5 text-xl font-bold">{visual.offersTitle}</h4>{selected.offers.map((offer) => <div key={offer.id} className="mt-3 rounded-xl border border-white/20 p-3 text-left"><div className="font-semibold">{offer.title}</div><div className="text-sm">R$ {offer.price_promotional.toFixed(2)}</div></div>)}<p className="pt-4 text-xs opacity-70">{visual.footerText}</p></div></div></div>
          <div className="rounded-2xl border border-surface-03 bg-surface-01 p-4"><h3 className="font-semibold text-cream">Ofertas vinculadas</h3>{selected.offers.length === 0 ? <p className="mt-3 text-sm text-stone">Adicione ofertas pela API de ofertas estratégicas antes de publicar.</p> : <div className="mt-3 grid gap-2 md:grid-cols-2">{selected.offers.map((offer: ApiStrategicOffer) => <div key={offer.id} className="rounded-lg bg-surface-02 p-3 text-sm text-parchment"><div className="font-semibold">{offer.code} · {offer.title}</div><div className="text-stone">{offer.highlighted ? "Destaque · " : ""}{offer.button_text || "Comprar"}</div></div>)}</div>}</div>
        </div> : <div className="rounded-2xl border border-dashed border-surface-03 p-10 text-center text-stone">Selecione ou crie uma campanha.</div>}
       {selected && <section className="rounded-2xl border border-surface-03 bg-surface-01 p-4"><h3 className="font-semibold text-cream">Marketing e indicadores</h3><div className="mt-3 grid gap-3 md:grid-cols-2"><label className="text-xs text-parchment">Orçamento planejado<input type="number" min="0" step="0.01" value={marketing.planned_budget ?? ""} onChange={(e) => setMarketing({ ...marketing, planned_budget: e.target.value === "" ? null : Number(e.target.value) })} className="mt-1 w-full rounded-lg bg-surface-03 px-3 py-2 text-sm text-cream" /></label><label className="text-xs text-parchment">Campanha de tráfego vinculada<input value={marketing.traffic_campaign_id ?? ""} onChange={(e) => setMarketing({ ...marketing, traffic_campaign_id: e.target.value || null })} className="mt-1 w-full rounded-lg bg-surface-03 px-3 py-2 text-sm text-cream" /></label></div><p className="mt-2 text-xs text-stone">Salve o rascunho para persistir a configuração.</p>{metrics ? <div className="mt-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">{[["Sessões", metrics.funnel.sessions], ["Visualizações", metrics.funnel.views], ["Cliques", metrics.funnel.offer_clicks], ["Pedidos pagos", metrics.funnel.paid_orders], ["Receita", `R$ ${metrics.revenue.toFixed(2)}`], ["Conversão", metrics.conversion_rate == null ? "—" : `${metrics.conversion_rate}%`], ["Gasto real", metrics.spend == null ? "—" : `R$ ${metrics.spend.toFixed(2)}`], ["ROAS", metrics.roas == null ? "—" : metrics.roas]].map(([label, value]) => <div key={String(label)} className="rounded-lg bg-surface-02 p-3 text-parchment"><span className="block text-xs text-stone">{label}</span><strong>{value}</strong></div>)}</div> : <p className="mt-3 text-sm text-stone">Ainda não há indicadores atribuídos.</p>}{metrics?.attribution.warning && <p className="mt-3 text-xs text-gold">{metrics.attribution.warning}</p>}</section>}
       </section>
    </main>
  </div>;
}
