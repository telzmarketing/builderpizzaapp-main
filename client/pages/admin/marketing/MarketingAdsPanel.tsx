import { useEffect, useState, useCallback } from "react";
import {
  Loader2, RefreshCw, TrendingUp, MousePointerClick,
  Eye, ShoppingCart, DollarSign, Zap, BarChart2,
  Link2, Users, Target, PieChart, Plus, Trash2, Copy,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (j: any) => j?.data ?? j;

const PLATFORMS = ["meta", "google", "tiktok"] as const;
type Platform = (typeof PLATFORMS)[number];
type Tab = "campanhas" | "utms" | "leads" | "pixels" | "roi";

const PLATFORM_META: Record<Platform, { label: string; emoji: string; color: string }> = {
  meta:   { label: "Meta Ads",    emoji: "📘", color: "text-blue-400" },
  google: { label: "Google Ads",  emoji: "🎯", color: "text-green-400" },
  tiktok: { label: "TikTok Ads",  emoji: "🎵", color: "text-pink-400" },
};

const TABS_CFG: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "campanhas", label: "Campanhas",          icon: BarChart2 },
  { id: "utms",      label: "UTMs",               icon: Link2 },
  { id: "leads",     label: "Tracking de Leads",  icon: Users },
  { id: "pixels",    label: "Pixels de Conversão",icon: Target },
  { id: "roi",       label: "Relatórios & ROI",   icon: PieChart },
];

interface Campaign {
  id: string; platform: Platform; external_id: string; name: string;
  status: string; objective: string; budget_daily: number;
  spend: number; impressions: number; clicks: number;
  conversions: number; revenue: number; ctr: number; cpc: number; cpa: number; roas: number;
  last_synced_at: string | null;
}
interface PlatformInsight {
  platform: string; total_spend: number; total_impressions: number; total_clicks: number;
  total_conversions: number; total_revenue: number; avg_roas: number; campaign_count: number;
}
interface Insights {
  period: string;
  by_platform: PlatformInsight[];
  totals: { total_spend: number; total_impressions: number; total_clicks: number; total_conversions: number; total_revenue: number; avg_roas: number; };
}
interface UtmLink {
  id: string; name: string; url: string; utm_source: string; utm_medium: string;
  utm_campaign: string; utm_term?: string; utm_content?: string;
  clicks: number; conversions: number; created_at: string;
}
interface LeadRow {
  id: string; customer_name?: string; phone?: string; email?: string;
  source: string; utm_source?: string; utm_campaign?: string;
  pipeline_stage?: string; value?: number; created_at: string;
}
interface PixelConfig {
  id: string; platform: string; pixel_id: string; enabled: boolean;
  events_tracked: string; created_at: string;
}
interface RoiReport {
  period: string; platform: string;
  spend: number; revenue: number; roas: number; roi_pct: number;
  leads: number; orders: number; cpl: number; cpo: number;
}

const fmt = (n: number, prefix = "") => `${prefix}${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtInt = (n: number) => n.toLocaleString("pt-BR");
function fmtDate(s?: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

const IC = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

export default function MarketingAdsPanel() {
  const [tab, setTab] = useState<Tab>("campanhas");

  // ── Campanhas ──
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState<Platform | "all" | null>(null);
  const [error, setError] = useState("");
  const [activePlatform, setActivePlatform] = useState<Platform | "all">("all");

  // ── UTMs ──
  const [utms, setUtms] = useState<UtmLink[]>([]);
  const [utmLoading, setUtmLoading] = useState(false);
  const [showUtmModal, setShowUtmModal] = useState(false);
  const [utmForm, setUtmForm] = useState({ name: "", url: "", utm_source: "", utm_medium: "", utm_campaign: "", utm_term: "", utm_content: "" });
  const [utmSaving, setUtmSaving] = useState(false);

  // ── Leads ──
  const [leads, setLeads] = useState<LeadRow[]>([]);
  const [leadsLoading, setLeadsLoading] = useState(false);

  // ── Pixels ──
  const [pixels, setPixels] = useState<PixelConfig[]>([]);
  const [pixelsLoading, setPixelsLoading] = useState(false);
  const [showPixelModal, setShowPixelModal] = useState(false);
  const [pixelForm, setPixelForm] = useState({ platform: "meta", pixel_id: "", events_tracked: "PageView,Purchase,Lead" });
  const [pixelSaving, setPixelSaving] = useState(false);

  // ── ROI ──
  const [roiPeriod, setRoiPeriod] = useState("30d");
  const [roiData, setRoiData] = useState<RoiReport[]>([]);
  const [roiLoading, setRoiLoading] = useState(false);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // ── Fetchers ──
  const fetchCampaigns = useCallback(() => {
    setLoading(true); setError("");
    Promise.all([
      fetch(`${BASE}/ads/campaigns`, { headers }).then(r => r.json()).then(unwrap),
      fetch(`${BASE}/ads/insights`, { headers }).then(r => r.json()).then(unwrap),
    ]).then(([cmp, ins]) => { setCampaigns(cmp ?? []); setInsights(ins); })
      .catch(() => setError("Falha ao carregar dados de anúncios."))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const fetchUtms = () => {
    setUtmLoading(true);
    fetch(`${BASE}/ads/utms`, { headers }).then(r => r.json()).then(d => setUtms(unwrap(d) ?? [])).catch(() => setUtms([]))
      .finally(() => setUtmLoading(false));
  };
  const fetchLeads = () => {
    setLeadsLoading(true);
    fetch(`${BASE}/ads/leads`, { headers }).then(r => r.json()).then(d => setLeads(unwrap(d) ?? [])).catch(() => setLeads([]))
      .finally(() => setLeadsLoading(false));
  };
  const fetchPixels = () => {
    setPixelsLoading(true);
    fetch(`${BASE}/ads/pixels`, { headers }).then(r => r.json()).then(d => setPixels(unwrap(d) ?? [])).catch(() => setPixels([]))
      .finally(() => setPixelsLoading(false));
  };
  const fetchRoi = (period: string) => {
    setRoiLoading(true);
    fetch(`${BASE}/ads/roi?period=${period}`, { headers }).then(r => r.json()).then(d => setRoiData(unwrap(d) ?? [])).catch(() => setRoiData([]))
      .finally(() => setRoiLoading(false));
  };

  useEffect(() => {
    if (tab === "campanhas") fetchCampaigns();
    if (tab === "utms")      fetchUtms();
    if (tab === "leads")     fetchLeads();
    if (tab === "pixels")    fetchPixels();
    if (tab === "roi")       fetchRoi(roiPeriod);
  }, [tab]); // eslint-disable-line

  const syncPlatform = async (platform: Platform | "all") => {
    setSyncing(platform);
    const url = platform === "all" ? `${BASE}/ads/sync-all` : `${BASE}/ads/${platform}/sync`;
    try { await fetch(url, { method: "POST", headers }); fetchCampaigns(); }
    catch { alert("Erro ao sincronizar."); } finally { setSyncing(null); }
  };

  // ── UTM CRUD ──
  const saveUtm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!utmForm.name.trim() || !utmForm.url.trim()) { alert("Nome e URL obrigatórios."); return; }
    setUtmSaving(true);
    try {
      await fetch(`${BASE}/ads/utms`, { method: "POST", headers, body: JSON.stringify(utmForm) });
      setShowUtmModal(false);
      setUtmForm({ name: "", url: "", utm_source: "", utm_medium: "", utm_campaign: "", utm_term: "", utm_content: "" });
      fetchUtms();
    } catch { alert("Erro ao criar link UTM."); } finally { setUtmSaving(false); }
  };
  const deleteUtm = async (id: string) => {
    if (!confirm("Excluir link UTM?")) return;
    await fetch(`${BASE}/ads/utms/${id}`, { method: "DELETE", headers });
    fetchUtms();
  };
  const buildUtmUrl = () => {
    const params = new URLSearchParams();
    if (utmForm.utm_source)   params.set("utm_source", utmForm.utm_source);
    if (utmForm.utm_medium)   params.set("utm_medium", utmForm.utm_medium);
    if (utmForm.utm_campaign) params.set("utm_campaign", utmForm.utm_campaign);
    if (utmForm.utm_term)     params.set("utm_term", utmForm.utm_term);
    if (utmForm.utm_content)  params.set("utm_content", utmForm.utm_content);
    const qs = params.toString();
    return utmForm.url ? `${utmForm.url}${qs ? "?" + qs : ""}` : "";
  };

  // ── Pixel CRUD ──
  const savePixel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pixelForm.pixel_id.trim()) { alert("Pixel ID obrigatório."); return; }
    setPixelSaving(true);
    try {
      await fetch(`${BASE}/ads/pixels`, { method: "POST", headers, body: JSON.stringify(pixelForm) });
      setShowPixelModal(false);
      setPixelForm({ platform: "meta", pixel_id: "", events_tracked: "PageView,Purchase,Lead" });
      fetchPixels();
    } catch { alert("Erro ao salvar pixel."); } finally { setPixelSaving(false); }
  };
  const togglePixel = async (id: string, enabled: boolean) => {
    await fetch(`${BASE}/ads/pixels/${id}`, { method: "PATCH", headers, body: JSON.stringify({ enabled: !enabled }) });
    fetchPixels();
  };
  const deletePixel = async (id: string) => {
    if (!confirm("Remover pixel?")) return;
    await fetch(`${BASE}/ads/pixels/${id}`, { method: "DELETE", headers });
    fetchPixels();
  };

  const filteredCampaigns = activePlatform === "all" ? campaigns : campaigns.filter(c => c.platform === activePlatform);
  const { totals } = insights ?? { totals: null };

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Tráfego Pago</h1>
          </div>
          {tab === "campanhas" && (
            <div className="flex items-center gap-2">
              <button onClick={() => syncPlatform("all")} disabled={!!syncing}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60">
                {syncing === "all" ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                Sincronizar tudo
              </button>
              <button onClick={fetchCampaigns} className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors">
                <RefreshCw size={16} />
              </button>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-1 bg-surface-02 border border-surface-03 rounded-xl p-1">
          {TABS_CFG.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${tab === id ? "bg-gold text-black" : "text-stone hover:text-cream hover:bg-surface-03"}`}>
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {/* ═══ CAMPANHAS ═══ */}
        {tab === "campanhas" && (
          <>
            {loading && <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>}
            {error && !loading && <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>}
            {!loading && !error && (
              <>
                {totals && (
                  <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
                    {[
                      { label: "Gasto total",  value: fmt(totals.total_spend, "R$ "),             icon: DollarSign,      color: "text-gold",       bg: "bg-gold/10" },
                      { label: "Impressões",   value: fmtInt(totals.total_impressions),            icon: Eye,             color: "text-blue-400",   bg: "bg-blue-500/10" },
                      { label: "Cliques",      value: fmtInt(totals.total_clicks),                 icon: MousePointerClick,color: "text-purple-400", bg: "bg-purple-500/10" },
                      { label: "Conversões",   value: fmtInt(totals.total_conversions),            icon: ShoppingCart,    color: "text-green-400",  bg: "bg-green-500/10" },
                      { label: "Receita",      value: fmt(totals.total_revenue, "R$ "),            icon: TrendingUp,      color: "text-emerald-400",bg: "bg-emerald-500/10" },
                      { label: "ROAS médio",   value: `${totals.avg_roas.toFixed(2)}x`,            icon: BarChart2,       color: "text-orange-400", bg: "bg-orange-500/10" },
                    ].map(m => (
                      <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-stone">{m.label}</span>
                          <div className={`p-1.5 rounded-lg ${m.bg}`}><m.icon size={14} className={m.color} /></div>
                        </div>
                        <p className={`text-xl font-bold ${m.color}`}>{m.value}</p>
                      </div>
                    ))}
                  </div>
                )}

                {insights?.by_platform?.length ? (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {insights.by_platform.map(p => {
                      const meta = PLATFORM_META[p.platform as Platform] ?? { label: p.platform, emoji: "📊", color: "text-stone" };
                      return (
                        <div key={p.platform} className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xl">{meta.emoji}</span>
                              <span className={`font-semibold text-sm ${meta.color}`}>{meta.label}</span>
                            </div>
                            <button onClick={() => syncPlatform(p.platform as Platform)} disabled={!!syncing}
                              className="p-1.5 rounded-lg bg-surface-03 text-stone hover:text-cream transition-colors disabled:opacity-40">
                              {syncing === p.platform ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                            </button>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            {[["Gasto", fmt(p.total_spend, "R$ ")], ["Receita", fmt(p.total_revenue, "R$ ")], ["Cliques", fmtInt(p.total_clicks)], ["ROAS", `${p.avg_roas.toFixed(2)}x`]].map(([l, v]) => (
                              <div key={l}><p className="text-stone">{l}</p><p className="text-cream font-medium">{v}</p></div>
                            ))}
                          </div>
                          <p className="text-xs text-stone">{p.campaign_count} campanha(s)</p>
                        </div>
                      );
                    })}
                  </div>
                ) : null}

                <div className="flex items-center gap-2 flex-wrap">
                  {(["all", ...PLATFORMS] as const).map(p => (
                    <button key={p} onClick={() => setActivePlatform(p)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors border ${activePlatform === p ? "bg-gold text-black border-gold" : "bg-surface-02 border-surface-03 text-stone hover:text-cream"}`}>
                      {p === "all" ? "Todas" : `${PLATFORM_META[p].emoji} ${PLATFORM_META[p].label}`}
                    </button>
                  ))}
                </div>

                <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
                  {filteredCampaigns.length ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-stone text-xs border-b border-surface-03">
                            {["Campanha", "Status", "Gasto", "Impr.", "Cliques", "CTR", "Conv.", "ROAS"].map(h => (
                              <th key={h} className="text-left px-4 py-3">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-surface-03">
                          {filteredCampaigns.map(c => {
                            const meta = PLATFORM_META[c.platform] ?? { emoji: "📊" };
                            return (
                              <tr key={c.id} className="hover:bg-surface-03/30 transition-colors">
                                <td className="px-4 py-3">
                                  <div className="flex items-center gap-2">
                                    <span>{meta.emoji}</span>
                                    <div><p className="text-cream font-medium text-xs truncate max-w-[180px]">{c.name || c.external_id}</p><p className="text-stone text-xs">{c.objective || "—"}</p></div>
                                  </div>
                                </td>
                                <td className="px-4 py-3">
                                  <span className={`text-xs px-2 py-0.5 rounded-full ${c.status === "ACTIVE" ? "bg-green-500/15 text-green-400" : c.status === "PAUSED" ? "bg-yellow-500/15 text-yellow-400" : "bg-surface-03 text-stone"}`}>{c.status || "—"}</span>
                                </td>
                                <td className="px-4 py-3 text-cream text-xs">{fmt(c.spend, "R$ ")}</td>
                                <td className="px-4 py-3 text-stone text-xs">{fmtInt(c.impressions)}</td>
                                <td className="px-4 py-3 text-stone text-xs">{fmtInt(c.clicks)}</td>
                                <td className="px-4 py-3 text-stone text-xs">{(c.ctr * 100).toFixed(2)}%</td>
                                <td className="px-4 py-3 text-stone text-xs">{fmtInt(c.conversions)}</td>
                                <td className="px-4 py-3 text-cream font-medium text-xs">{c.roas.toFixed(2)}x</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="py-16 text-center"><p className="text-stone text-sm">Nenhuma campanha. Clique em "Sincronizar tudo".</p></div>
                  )}
                </div>
              </>
            )}
          </>
        )}

        {/* ═══ UTMs ═══ */}
        {tab === "utms" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{utms.length} link(s) rastreáveis</p>
              <button onClick={() => setShowUtmModal(true)}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Novo Link UTM
              </button>
            </div>
            {utmLoading ? <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div> : (
              <>
                {utms.length === 0 ? (
                  <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                    <Link2 size={40} className="text-surface-03 mb-3" />
                    <p className="text-stone text-sm">Nenhum link UTM criado.</p>
                  </div>
                ) : (
                  <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                            {["Nome", "Fonte", "Meio", "Campanha", "Cliques", "Conv.", "Criado"].map(h => (
                              <th key={h} className="text-left p-3">{h}</th>
                            ))}
                            <th className="p-3" />
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-surface-03">
                          {utms.map(u => (
                            <tr key={u.id} className="hover:bg-surface-03/30 transition-colors">
                              <td className="p-3">
                                <p className="text-cream font-medium text-xs">{u.name}</p>
                                <button onClick={() => navigator.clipboard.writeText(`${u.url}?utm_source=${u.utm_source}&utm_medium=${u.utm_medium}&utm_campaign=${u.utm_campaign}${u.utm_term ? "&utm_term=" + u.utm_term : ""}${u.utm_content ? "&utm_content=" + u.utm_content : ""}`)}
                                  className="flex items-center gap-1 text-gold hover:text-gold/80 text-xs mt-0.5">
                                  <Copy size={10} /> Copiar URL
                                </button>
                              </td>
                              <td className="p-3 text-stone text-xs">{u.utm_source}</td>
                              <td className="p-3 text-stone text-xs">{u.utm_medium}</td>
                              <td className="p-3 text-stone text-xs">{u.utm_campaign}</td>
                              <td className="p-3 text-cream font-medium">{u.clicks.toLocaleString("pt-BR")}</td>
                              <td className="p-3 text-green-400">{u.conversions.toLocaleString("pt-BR")}</td>
                              <td className="p-3 text-stone text-xs">{fmtDate(u.created_at)}</td>
                              <td className="p-3">
                                <button onClick={() => deleteUtm(u.id)} className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors">
                                  <Trash2 size={13} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* ═══ LEADS ═══ */}
        {tab === "leads" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{leads.length} lead(s) rastreado(s)</p>
              <button onClick={fetchLeads} className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors"><RefreshCw size={16} /></button>
            </div>
            {leadsLoading ? <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div> : (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
                {leads.length === 0 ? (
                  <div className="flex flex-col items-center py-16">
                    <Users size={40} className="text-surface-03 mb-3" />
                    <p className="text-stone text-sm">Nenhum lead rastreado.</p>
                    <p className="text-stone/60 text-xs mt-1">Os leads são registrados automaticamente a partir dos parâmetros UTM.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                          {["Cliente", "Contato", "Fonte", "Campanha", "Etapa Pipeline", "Valor", "Data"].map(h => (
                            <th key={h} className="text-left p-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {leads.map(l => (
                          <tr key={l.id} className="hover:bg-surface-03/30 transition-colors">
                            <td className="p-3 text-cream font-medium text-xs">{l.customer_name ?? "—"}</td>
                            <td className="p-3 text-stone text-xs">{l.phone ?? l.email ?? "—"}</td>
                            <td className="p-3 text-stone text-xs">{l.utm_source ?? l.source ?? "—"}</td>
                            <td className="p-3 text-stone text-xs">{l.utm_campaign ?? "—"}</td>
                            <td className="p-3 text-stone text-xs">{l.pipeline_stage ?? "—"}</td>
                            <td className="p-3 text-gold text-xs">{l.value ? fmt(l.value, "R$ ") : "—"}</td>
                            <td className="p-3 text-stone text-xs">{fmtDate(l.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ═══ PIXELS ═══ */}
        {tab === "pixels" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-stone text-sm">{pixels.length} pixel(s) configurado(s)</p>
              <button onClick={() => setShowPixelModal(true)}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Adicionar Pixel
              </button>
            </div>
            {pixelsLoading ? <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div> : (
              <>
                {pixels.length === 0 ? (
                  <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                    <Target size={40} className="text-surface-03 mb-3" />
                    <p className="text-stone text-sm">Nenhum pixel configurado.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {pixels.map(px => (
                      <div key={px.id} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">{px.platform === "meta" ? "📘" : px.platform === "google" ? "🎯" : px.platform === "tiktok" ? "🎵" : "📊"}</span>
                            <div>
                              <p className="text-cream font-semibold text-sm capitalize">{px.platform} Pixel</p>
                              <p className="text-stone text-xs font-mono">{px.pixel_id}</p>
                            </div>
                          </div>
                          <button onClick={() => togglePixel(px.id, px.enabled)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${px.enabled ? "bg-gold" : "bg-surface-03"}`}>
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${px.enabled ? "translate-x-6" : "translate-x-1"}`} />
                          </button>
                        </div>
                        <div>
                          <p className="text-xs text-stone mb-1">Eventos rastreados:</p>
                          <div className="flex flex-wrap gap-1">
                            {px.events_tracked.split(",").filter(Boolean).map(ev => (
                              <span key={ev} className="px-2 py-0.5 bg-surface-03 text-stone text-xs rounded">{ev.trim()}</span>
                            ))}
                          </div>
                        </div>
                        <button onClick={() => deletePixel(px.id)} className="flex items-center gap-1.5 text-xs text-stone hover:text-red-400 transition-colors">
                          <Trash2 size={12} /> Remover
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* ═══ ROI ═══ */}
        {tab === "roi" && (
          <>
            <div className="flex items-center gap-3">
              <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                {["7d", "30d", "90d"].map(p => (
                  <button key={p} onClick={() => { setRoiPeriod(p); fetchRoi(p); }}
                    className={`px-4 py-2 text-sm font-medium transition-colors ${roiPeriod === p ? "bg-gold text-black" : "text-stone hover:text-cream"}`}>
                    {p === "7d" ? "7 dias" : p === "30d" ? "30 dias" : "90 dias"}
                  </button>
                ))}
              </div>
              <button onClick={() => fetchRoi(roiPeriod)} className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors">
                <RefreshCw size={16} />
              </button>
            </div>
            {roiLoading ? <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div> : (
              roiData.length === 0 ? (
                <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                  <PieChart size={40} className="text-surface-03 mb-3" />
                  <p className="text-stone text-sm">Sem dados de ROI para o período.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {roiData.map((r, i) => (
                    <div key={i} className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                      <div className="flex items-center gap-2 mb-4">
                        <span className="text-xl">{r.platform === "meta" ? "📘" : r.platform === "google" ? "🎯" : "🎵"}</span>
                        <h3 className="text-cream font-semibold text-sm capitalize">{r.platform} Ads — {r.period}</h3>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
                        {[
                          { label: "Gasto",     value: fmt(r.spend, "R$ "),        cls: "text-red-400" },
                          { label: "Receita",   value: fmt(r.revenue, "R$ "),      cls: "text-green-400" },
                          { label: "ROAS",      value: `${r.roas.toFixed(2)}x`,    cls: "text-gold" },
                          { label: "ROI",       value: `${r.roi_pct.toFixed(1)}%`, cls: r.roi_pct >= 0 ? "text-green-400" : "text-red-400" },
                          { label: "Leads",     value: String(r.leads),            cls: "text-blue-400" },
                          { label: "Pedidos",   value: String(r.orders),           cls: "text-emerald-400" },
                          { label: "CPL",       value: fmt(r.cpl, "R$ "),          cls: "text-orange-400" },
                          { label: "CPO",       value: fmt(r.cpo, "R$ "),          cls: "text-purple-400" },
                        ].map(m => (
                          <div key={m.label}>
                            <p className="text-xs text-stone">{m.label}</p>
                            <p className={`text-sm font-bold ${m.cls}`}>{m.value}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )
            )}
          </>
        )}
      </main>

      {/* ── UTM Modal ── */}
      {showUtmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">Novo Link UTM</h2>
              <button onClick={() => setShowUtmModal(false)} className="text-stone hover:text-cream"><span>✕</span></button>
            </div>
            <form onSubmit={saveUtm} className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-xs text-stone">Nome *</label>
                <input type="text" value={utmForm.name} onChange={e => setUtmForm(f => ({ ...f, name: e.target.value }))} placeholder="Ex: Post Instagram Black Friday" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">URL Base *</label>
                <input type="url" value={utmForm.url} onChange={e => setUtmForm(f => ({ ...f, url: e.target.value }))} placeholder="https://delivery.moschettieri.com.br" className={IC} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { key: "utm_source", label: "Fonte (utm_source)", placeholder: "instagram" },
                  { key: "utm_medium", label: "Meio (utm_medium)", placeholder: "post" },
                  { key: "utm_campaign", label: "Campanha (utm_campaign)", placeholder: "black_friday_2025" },
                  { key: "utm_term", label: "Termo (utm_term)", placeholder: "pizza" },
                ].map(({ key, label, placeholder }) => (
                  <div key={key} className="space-y-1">
                    <label className="text-xs text-stone">{label}</label>
                    <input type="text" value={(utmForm as Record<string, string>)[key]} onChange={e => setUtmForm(f => ({ ...f, [key]: e.target.value }))} placeholder={placeholder} className={IC} />
                  </div>
                ))}
              </div>
              {buildUtmUrl() && (
                <div className="bg-surface-03 rounded-xl p-3">
                  <p className="text-xs text-stone mb-1">URL gerada:</p>
                  <p className="text-xs text-gold font-mono break-all">{buildUtmUrl()}</p>
                </div>
              )}
              <div className="flex gap-3">
                <button type="button" onClick={() => setShowUtmModal(false)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                <button type="submit" disabled={utmSaving} className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {utmSaving && <Loader2 size={14} className="animate-spin" />} Criar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Pixel Modal ── */}
      {showPixelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">Adicionar Pixel</h2>
              <button onClick={() => setShowPixelModal(false)} className="text-stone hover:text-cream"><span>✕</span></button>
            </div>
            <form onSubmit={savePixel} className="p-5 space-y-4">
              <div className="space-y-1">
                <label className="text-xs text-stone">Plataforma</label>
                <select value={pixelForm.platform} onChange={e => setPixelForm(f => ({ ...f, platform: e.target.value }))} className={IC}>
                  <option value="meta">Meta (Facebook/Instagram)</option>
                  <option value="google">Google Ads</option>
                  <option value="tiktok">TikTok Ads</option>
                  <option value="pinterest">Pinterest</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Pixel ID *</label>
                <input type="text" value={pixelForm.pixel_id} onChange={e => setPixelForm(f => ({ ...f, pixel_id: e.target.value }))} placeholder="123456789012345" className={IC} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-stone">Eventos rastreados (separados por vírgula)</label>
                <input type="text" value={pixelForm.events_tracked} onChange={e => setPixelForm(f => ({ ...f, events_tracked: e.target.value }))} placeholder="PageView,Purchase,Lead,AddToCart" className={IC} />
              </div>
              <div className="flex gap-3">
                <button type="button" onClick={() => setShowPixelModal(false)} className="flex-1 py-2 rounded-xl border border-surface-03 text-stone text-sm">Cancelar</button>
                <button type="submit" disabled={pixelSaving} className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {pixelSaving && <Loader2 size={14} className="animate-spin" />} Salvar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
