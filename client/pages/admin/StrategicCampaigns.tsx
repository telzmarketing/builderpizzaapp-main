import { useEffect, useMemo, useState, type FormEvent } from "react";
import { CalendarDays, ChevronRight, Layers3, Loader2, Plus, Search, Target } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { strategicCampaignsApi, type ApiStrategicCampaign, type StrategicCampaignStatus } from "@/lib/api";
import { campaignStatusLabel, filterStrategicCampaigns, strategicCampaignSummary, type CampaignPeriodFilter } from "@/lib/strategicCampaignAdmin";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const statuses: Array<["all" | StrategicCampaignStatus, string]> = [["all", "Todos os status"], ["draft", "Rascunho"], ["scheduled", "Agendada"], ["active", "Ativa"], ["paused", "Pausada"], ["sold_out", "Esgotada"], ["ended", "Encerrada"], ["archived", "Arquivada"]];
const periods: Array<[CampaignPeriodFilter, string]> = [["all", "Qualquer período"], ["current", "Em andamento"], ["upcoming", "Próximas"], ["past", "Finalizadas"], ["undated", "Sem período"]];
const blank = { name: "", commercial_name: "", slug: "", description: "", starts_at: "", ends_at: "" };
const iso = (value: string) => value ? new Date(value).toISOString() : null;
const date = (value: string | null) => value ? new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value)) : "—";

function Status({ value }: { value: StrategicCampaignStatus }) {
  const tone = { draft: "text-stone", scheduled: "text-sky-300", active: "text-emerald-300", paused: "text-amber-300", sold_out: "text-rose-300", ended: "text-violet-300", archived: "text-slate-300" }[value];
  return <span className={`rounded-full border border-current/30 bg-current/10 px-2.5 py-1 text-xs font-semibold ${tone}`}>{campaignStatusLabel(value)}</span>;
}

export default function StrategicCampaigns() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<ApiStrategicCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | StrategicCampaignStatus>("all");
  const [period, setPeriod] = useState<CampaignPeriodFilter>("all");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(blank);
  const [formError, setFormError] = useState<string | null>(null);

  const load = async () => { setLoading(true); setError(null); try { setCampaigns(await strategicCampaignsApi.list()); } catch (cause) { setError(cause instanceof Error ? cause.message : "Não foi possível carregar as campanhas."); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  const summary = useMemo(() => strategicCampaignSummary(campaigns), [campaigns]);
  const visible = useMemo(() => filterStrategicCampaigns(campaigns, { query, status, period }), [campaigns, query, status, period]);

  const create = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setFormError(null);
    try {
      const created = await strategicCampaignsApi.create({ name: form.name.trim(), commercial_name: form.commercial_name.trim() || null, slug: form.slug.trim(), description: form.description.trim() || null, starts_at: iso(form.starts_at), ends_at: iso(form.ends_at) });
      setOpen(false); setForm(blank); navigate(`/painel/marketing/campanhas-estrategicas/${created.id}/visao-geral`);
    } catch (cause) { setFormError(cause instanceof Error ? cause.message : "Não foi possível criar a campanha."); } finally { setSaving(false); }
  };

  return <div className="min-w-0 space-y-6">
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.2em] text-gold">Marketing / Campanhas estratégicas</p><h1 className="mt-1 text-2xl font-black text-cream md:text-3xl">Gestão de campanhas</h1><p className="mt-1 text-sm text-stone">Planeje, acompanhe e organize campanhas comerciais.</p></div><Button onClick={() => setOpen(true)} className="bg-gold font-bold text-surface-00 hover:bg-gold/90"><Plus /> Nova campanha</Button></header>
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicadores gerais">{[["Total de campanhas", summary.total, Layers3], ["Campanhas ativas", summary.active, Target], ["Agendadas", summary.scheduled, CalendarDays], ["Ofertas vinculadas", summary.offers, Layers3]].map(([label, value, Icon]) => { const I = Icon as typeof Layers3; return <article key={String(label)} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex justify-between text-sm text-stone"><span>{String(label)}</span><I className="h-4 w-4 text-gold" /></div><strong className="mt-3 block text-3xl text-cream">{loading ? "—" : String(value)}</strong></article>; })}</section>
    <section className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
      <div className="grid gap-3 border-b border-surface-03 p-4 md:grid-cols-[1fr_210px_210px]"><label className="relative"><span className="sr-only">Pesquisar campanhas</span><Search className="absolute left-3 top-3 h-4 w-4 text-stone" /><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar por nome, slug ou descrição" className="border-surface-03 bg-surface-01 pl-9 text-cream" /></label><select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value as typeof status)} className="rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream">{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select aria-label="Período" value={period} onChange={(e) => setPeriod(e.target.value as CampaignPeriodFilter)} className="rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream">{periods.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
      {loading && <State><Loader2 className="animate-spin text-gold" /> Carregando campanhas...</State>}
      {!loading && error && <State><strong className="text-cream">Falha ao carregar campanhas</strong><span>{error}</span><Button variant="outline" onClick={() => void load()}>Tentar novamente</Button></State>}
      {!loading && !error && visible.length === 0 && <State><Layers3 className="h-8 w-8 text-gold" /><strong className="text-cream">{campaigns.length ? "Nenhuma campanha encontrada" : "Nenhuma campanha criada"}</strong><span>{campaigns.length ? "Ajuste os filtros para ver outros resultados." : "Crie sua primeira campanha para começar."}</span>{!campaigns.length && <Button onClick={() => setOpen(true)} className="bg-gold text-surface-00"><Plus /> Nova campanha</Button>}</State>}
      {!loading && !error && visible.map((item) => <button key={item.id} onClick={() => navigate(`/painel/marketing/campanhas-estrategicas/${item.id}/visao-geral`)} className="grid w-full gap-3 border-b border-surface-03 p-4 text-left hover:bg-surface-03/40 md:grid-cols-[1fr_190px_130px_140px_20px] md:items-center"><div className="min-w-0"><div className="flex items-center gap-2"><strong className="truncate text-sm text-cream">{item.name}</strong><Status value={item.status} /></div><p className="mt-1 truncate text-xs text-stone">{item.commercial_name || item.description || `/${item.slug}`}</p></div><span className="text-xs text-parchment">{item.starts_at || item.ends_at ? `${date(item.starts_at)} — ${date(item.ends_at)}` : "Período não definido"}</span><span className="text-sm text-cream">{item.offers.length} ofertas</span><span className="text-xs text-stone">{item.published_version ? `Publicada v${item.published_version}` : "Não publicada"}</span><ChevronRight className="hidden h-4 w-4 text-stone md:block" /></button>)}
    </section>
    <Dialog open={open} onOpenChange={(value) => { if (!saving) { setOpen(value); setFormError(null); } }}><DialogContent className="max-w-2xl border-surface-03 bg-surface-02 text-cream"><DialogHeader><DialogTitle>Nova campanha</DialogTitle><DialogDescription className="text-stone">Cadastre os dados iniciais e continue na página da campanha.</DialogDescription></DialogHeader><form onSubmit={create} className="space-y-4">{formError && <div role="alert" className="rounded-lg bg-rose-400/10 p-3 text-sm text-rose-200">{formError}</div>}<div className="grid gap-4 sm:grid-cols-2"><Field label="Nome administrativo"><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><Field label="Nome comercial"><Input value={form.commercial_name} onChange={(e) => setForm({ ...form, commercial_name: e.target.value })} /></Field></div><Field label="Slug da URL"><Input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-+/g, "-") })} placeholder="black-friday-2026" /></Field><Field label="Descrição"><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field><div className="grid gap-4 sm:grid-cols-2"><Field label="Início"><Input type="datetime-local" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} /></Field><Field label="Término"><Input type="datetime-local" min={form.starts_at || undefined} value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} /></Field></div><DialogFooter className="gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancelar</Button><Button disabled={saving} className="bg-gold text-surface-00">{saving ? <Loader2 className="animate-spin" /> : <Plus />} Criar campanha</Button></DialogFooter></form></DialogContent></Dialog>
  </div>;
}

function State({ children }: { children: React.ReactNode }) { return <div className="flex min-h-64 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-stone">{children}</div>; }
function Field({ label, children }: { label: string; children: React.ReactElement }) { return <label className="space-y-1.5 text-sm text-parchment">{label}{children}</label>; }
