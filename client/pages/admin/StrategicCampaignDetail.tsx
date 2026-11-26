import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { ArrowLeft, CalendarClock, ChartNoAxesCombined, CircleDollarSign, ExternalLink, FileImage, Gauge, LayoutDashboard, Loader2, Megaphone, PackageOpen, Save, Settings2, ShoppingBag } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { strategicCampaignsApi, type ApiStrategicCampaign, type StrategicCampaignMetrics } from "@/lib/api";
import { campaignStatusLabel } from "@/lib/strategicCampaignAdmin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import StrategicCampaignOffersTab from "@/components/admin/strategic-campaigns/StrategicCampaignOffersTab";
import StrategicCampaignLandingEditor from "@/components/admin/strategic-campaigns/StrategicCampaignLandingEditor";
import StrategicCampaignCommercialTab from "@/components/admin/strategic-campaigns/StrategicCampaignCommercialTab";
import StrategicCampaignCapacityTab from "@/components/admin/strategic-campaigns/StrategicCampaignCapacityTab";
import StrategicCampaignReservationsTab from "@/components/admin/strategic-campaigns/StrategicCampaignReservationsTab";

const basePath = "/painel/marketing/campanhas-estrategicas";
const tabs = [
  ["visao-geral", "Visão geral", LayoutDashboard], ["configuracoes-gerais", "Configurações gerais", Settings2], ["ofertas", "Ofertas", ShoppingBag],
  ["landing-page", "Landing Page", FileImage], ["comercializacao", "Comercialização", PackageOpen], ["agendamento-capacidade", "Agendamento e capacidade", CalendarClock],
  ["pedidos-reservas", "Pedidos e reservas", Gauge], ["marketing-rastreamento", "Marketing e rastreamento", Megaphone], ["resultados-financeiros", "Resultados financeiros", CircleDollarSign],
] as const;
type Section = typeof tabs[number][0];
const validSections = new Set<string>(tabs.map(([section]) => section));
const money = (value: number | null | undefined) => value == null ? "—" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
const localDateTime = (value: string | null) => value ? new Date(value).toISOString().slice(0, 16) : "";

export default function StrategicCampaignDetail() {
  const { campaignId, section } = useParams<{ campaignId: string; section?: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<ApiStrategicCampaign | null>(null);
  const [metrics, setMetrics] = useState<StrategicCampaignMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeSection: Section = validSections.has(section || "") ? section as Section : "visao-geral";

  const load = async () => {
    if (!campaignId) return;
    setLoading(true); setError(null);
    try {
      const loaded = await strategicCampaignsApi.get(campaignId);
      setCampaign(loaded);
      void strategicCampaignsApi.metrics(campaignId).then(setMetrics).catch(() => setMetrics(null));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Não foi possível carregar a campanha."); } finally { setLoading(false); }
  };

  useEffect(() => { if (campaignId && !validSections.has(section || "")) navigate(`${basePath}/${campaignId}/visao-geral`, { replace: true }); }, [campaignId, navigate, section]);
  useEffect(() => { void load(); }, [campaignId]);

  if (loading) return <PageState><Loader2 className="h-6 w-6 animate-spin text-gold" /> Carregando campanha...</PageState>;
  if (error || !campaign) return <PageState><strong className="text-cream">Campanha indisponível</strong><span>{error || "A campanha informada não foi encontrada."}</span><div className="flex gap-2"><Button variant="outline" onClick={() => navigate(basePath)}>Voltar</Button><Button onClick={() => void load()} className="bg-gold text-surface-00">Tentar novamente</Button></div></PageState>;

  return <div className="min-w-0 space-y-5">
    <header className="space-y-4"><Link to={basePath} className="inline-flex items-center gap-2 text-sm text-stone hover:text-cream"><ArrowLeft className="h-4 w-4" /> Todas as campanhas</Link><div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-black text-cream md:text-3xl">{campaign.name}</h1><span className="rounded-full border border-gold/30 bg-gold/10 px-2.5 py-1 text-xs font-semibold text-gold">{campaignStatusLabel(campaign.status)}</span></div><p className="mt-1 text-sm text-stone">{campaign.commercial_name || campaign.description || `/${campaign.slug}`}</p></div><a href={`/campanha-estrategica/${campaign.slug}`} target="_blank" rel="noreferrer" className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-surface-03 px-4 text-sm font-medium text-parchment hover:bg-surface-03"><ExternalLink className="h-4 w-4" /> Visualizar página pública</a></div></header>
    <nav aria-label="Áreas da campanha" className="overflow-x-auto rounded-xl border border-surface-03 bg-surface-02 p-1"><div className="flex min-w-max gap-1">{tabs.map(([path, label, Icon]) => <Link key={path} to={`${basePath}/${campaign.id}/${path}`} className={`inline-flex items-center gap-2 rounded-lg px-3 py-2.5 text-xs font-semibold transition-colors ${activeSection === path ? "bg-gold text-surface-00" : "text-stone hover:bg-surface-03 hover:text-cream"}`}><Icon className="h-4 w-4" />{label}</Link>)}</div></nav>
    <section>{activeSection === "visao-geral" && <Overview campaign={campaign} metrics={metrics} />}{activeSection === "configuracoes-gerais" && <GeneralSettings campaign={campaign} onSaved={setCampaign} />}{activeSection === "ofertas" && <StrategicCampaignOffersTab campaign={campaign} onChanged={setCampaign} />}{activeSection === "landing-page" && <StrategicCampaignLandingEditor campaign={campaign} onChanged={setCampaign} />}{activeSection === "comercializacao" && <StrategicCampaignCommercialTab campaign={campaign} onChanged={setCampaign} />}{activeSection === "agendamento-capacidade" && <StrategicCampaignCapacityTab campaign={campaign} />}{activeSection === "pedidos-reservas" && <StrategicCampaignReservationsTab campaign={campaign} />}{activeSection === "marketing-rastreamento" && <Marketing campaign={campaign} metrics={metrics} />}{activeSection === "resultados-financeiros" && <Financial metrics={metrics} />}</section>
  </div>;
}

function Overview({ campaign, metrics }: { campaign: ApiStrategicCampaign; metrics: StrategicCampaignMetrics | null }) {
  return <div className="space-y-4"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Ofertas" value={campaign.offers.length} /><Metric label="Sessões" value={metrics?.funnel.sessions ?? "—"} /><Metric label="Pedidos pagos" value={metrics?.funnel.paid_orders ?? "—"} /><Metric label="Receita atribuída" value={money(metrics?.revenue)} /></div><Panel title="Resumo da campanha"><dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4"><Data label="Slug" value={`/${campaign.slug}`} /><Data label="Versão publicada" value={campaign.published_version ? `v${campaign.published_version}` : "Não publicada"} /><Data label="Início" value={formatDate(campaign.starts_at)} /><Data label="Término" value={formatDate(campaign.ends_at)} /></dl></Panel>{campaign.offers.length === 0 && <EmptySection icon={ShoppingBag} title="Campanha sem ofertas" description="A estrutura está pronta. Cadastre as ofertas na aba Ofertas quando a etapa comercial C2 for implementada." />}</div>;
}

function GeneralSettings({ campaign, onSaved }: { campaign: ApiStrategicCampaign; onSaved: (campaign: ApiStrategicCampaign) => void }) {
  const [form, setForm] = useState(() => ({ name: campaign.name, commercial_name: campaign.commercial_name || "", slug: campaign.slug, description: campaign.description || "", starts_at: localDateTime(campaign.starts_at), ends_at: localDateTime(campaign.ends_at) }));
  const [saving, setSaving] = useState(false); const [message, setMessage] = useState<string | null>(null); const [failed, setFailed] = useState(false);
  const save = async (event: FormEvent) => { event.preventDefault(); setSaving(true); setMessage(null); try { const updated = await strategicCampaignsApi.update(campaign.id, { name: form.name.trim(), commercial_name: form.commercial_name.trim() || null, slug: form.slug.trim(), description: form.description.trim() || null, starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null, ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null }); onSaved(updated); setFailed(false); setMessage("Configurações salvas com sucesso."); } catch (cause) { setFailed(true); setMessage(cause instanceof Error ? cause.message : "Não foi possível salvar."); } finally { setSaving(false); } };
  return <Panel title="Configurações gerais" description="Informações administrativas, URL e período principal da campanha."><form onSubmit={save} className="space-y-4">{message && <div role="status" className={`rounded-lg border p-3 text-sm ${failed ? "border-rose-400/30 bg-rose-400/10 text-rose-200" : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"}`}>{message}</div>}<div className="grid gap-4 md:grid-cols-2"><Field label="Nome administrativo"><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><Field label="Nome comercial"><Input value={form.commercial_name} onChange={(e) => setForm({ ...form, commercial_name: e.target.value })} /></Field></div><Field label="Slug da URL"><Input required value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-+/g, "-") })} /></Field><Field label="Descrição"><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field><div className="grid gap-4 md:grid-cols-2"><Field label="Início"><Input type="datetime-local" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} /></Field><Field label="Término"><Input type="datetime-local" min={form.starts_at || undefined} value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} /></Field></div><div className="flex justify-end"><Button disabled={saving} className="bg-gold text-surface-00">{saving ? <Loader2 className="animate-spin" /> : <Save />} Salvar alterações</Button></div></form></Panel>;
}

function Marketing({ campaign, metrics }: { campaign: ApiStrategicCampaign; metrics: StrategicCampaignMetrics | null }) { return <div className="space-y-4"><Panel title="Marketing e rastreamento"><dl className="grid gap-4 sm:grid-cols-3"><Data label="Orçamento planejado" value={money(campaign.marketing_config.planned_budget)} /><Data label="Campanha de tráfego" value={campaign.marketing_config.traffic_campaign_id || "Não vinculada"} /><Data label="Janela de atribuição" value={`${campaign.marketing_config.attribution_window_days} dias`} /></dl></Panel><div className="grid gap-3 sm:grid-cols-3"><Metric label="Sessões" value={metrics?.funnel.sessions ?? "—"} /><Metric label="Cliques em ofertas" value={metrics?.funnel.offer_clicks ?? "—"} /><Metric label="Conversão" value={metrics?.conversion_rate == null ? "—" : `${metrics.conversion_rate}%`} /></div></div>; }
function Financial({ metrics }: { metrics: StrategicCampaignMetrics | null }) { return <Panel title="Resultados financeiros" description="Indicadores atribuídos pelo contrato atual."><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Receita" value={money(metrics?.revenue)} /><Metric label="Investimento" value={money(metrics?.spend)} /><Metric label="ROAS" value={metrics?.roas ?? "—"} /><Metric label="Pedidos pagos" value={metrics?.funnel.paid_orders ?? "—"} /></div>{!metrics && <p className="mt-4 text-sm text-stone">Indicadores indisponíveis no momento. Recarregue a página para tentar novamente.</p>}</Panel>; }

function Panel({ title, description, children }: { title: string; description?: string; children: ReactNode }) { return <div className="rounded-2xl border border-surface-03 bg-surface-02 p-4 md:p-6"><h2 className="text-lg font-bold text-cream">{title}</h2>{description && <p className="mt-1 text-sm text-stone">{description}</p>}<div className="mt-5">{children}</div></div>; }
function Metric({ label, value }: { label: string; value: ReactNode }) { return <article className="rounded-xl border border-surface-03 bg-surface-02 p-4"><span className="text-xs text-stone">{label}</span><strong className="mt-2 block text-2xl text-cream">{value}</strong></article>; }
function Data({ label, value }: { label: string; value: ReactNode }) { return <div><dt className="text-xs text-stone">{label}</dt><dd className="mt-1 font-semibold text-parchment">{value}</dd></div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="space-y-1.5 text-sm text-parchment">{label}{children}</label>; }
function EmptySection({ icon: Icon, title, description }: { icon: typeof Gauge; title: string; description: string }) { return <div className="flex min-h-52 flex-col items-center justify-center rounded-xl border border-dashed border-surface-03 p-6 text-center"><span className="rounded-full bg-gold/10 p-3 text-gold"><Icon className="h-6 w-6" /></span><strong className="mt-3 text-cream">{title}</strong><p className="mt-1 max-w-lg text-sm text-stone">{description}</p></div>; }
function PageState({ children }: { children: ReactNode }) { return <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center text-sm text-stone">{children}</div>; }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Não definido"; }
