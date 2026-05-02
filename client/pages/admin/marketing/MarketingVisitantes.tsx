import { useEffect, useState } from "react";
import {
  Loader2, Users, Monitor, Smartphone, RefreshCw, Globe,
  Tablet, BarChart2, ArrowRight, MapPin, MousePointer, ShoppingCart,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type Period = "today" | "7d" | "30d" | "90d";

interface Visitor {
  id: string; city: string; browser: string; device: string;
  sessions: number; pageviews: number; last_seen: string;
}
interface CommonEvent { name: string; count: number; }
interface UtmRow      { source: string; medium: string; campaign: string; sessions: number; conversions: number; }
interface DeviceBreak { device_type: string; count: number; pct: number; }
interface TopProduct  { product_name: string; views: number; add_to_cart: number; orders: number; }
interface FunnelStep  { label: string; value: number; }

interface VisitorData {
  visitors_today: number;
  online_visitors: number;
  total_sessions: number;
  total_events: number;
  bounce_rate?: number;
  avg_session_duration?: number;
  recent_visitors: Visitor[];
  common_events: CommonEvent[];
  utm_breakdown?: UtmRow[];
  devices?: DeviceBreak[];
  top_products?: TopProduct[];
  funnel?: FunnelStep[];
}

const EMPTY: VisitorData = {
  visitors_today: 0, online_visitors: 0, total_sessions: 0, total_events: 0,
  bounce_rate: 0, avg_session_duration: 0,
  recent_visitors: [], common_events: [],
  utm_breakdown: [], devices: [], top_products: [],
  funnel: [
    { label: "Visitantes", value: 0 }, { label: "Produtos vistos", value: 0 },
    { label: "Adicionou ao carrinho", value: 0 }, { label: "Checkout", value: 0 },
    { label: "Pedido finalizado", value: 0 },
  ],
};

const PERIOD_LABELS: Record<Period, string> = { today: "Hoje", "7d": "7 dias", "30d": "30 dias", "90d": "90 dias" };

type ActiveTab = "visao_geral" | "utms" | "dispositivos" | "produtos" | "funil";
const TABS: { id: ActiveTab; label: string; icon: React.ElementType }[] = [
  { id: "visao_geral", label: "Visão Geral",       icon: BarChart2 },
  { id: "utms",        label: "UTMs",               icon: ArrowRight },
  { id: "dispositivos",label: "Dispositivos",       icon: Monitor },
  { id: "produtos",    label: "Top Produtos",       icon: ShoppingCart },
  { id: "funil",       label: "Funil de Conversão", icon: MousePointer },
];

function fmtDuration(seconds?: number) {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

export default function MarketingVisitantes() {
  const [period, setPeriod] = useState<Period>("7d");
  const [tab, setTab] = useState<ActiveTab>("visao_geral");
  const [data, setData] = useState<VisitorData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [warn, setWarn] = useState("");

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = (p: Period) => {
    setLoading(true);
    setWarn("");
    fetch(`${BASE}/marketing/visitors?period=${p}`, { headers })
      .then(r => r.json()).then(d => setData({ ...EMPTY, ...unwrap(d) }))
      .catch(() => setWarn("Não foi possível carregar dados de visitantes."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(period); }, [period]); // eslint-disable-line

  const maxEvent = Math.max(...(data.common_events ?? []).map(e => e.count), 1);
  const maxUtm   = Math.max(...(data.utm_breakdown ?? []).map(u => u.sessions), 1);
  const maxFunnel= Math.max(...(data.funnel ?? []).map(f => f.value), 1);

  const deviceIcon = (d: string) => {
    const dl = d?.toLowerCase();
    if (dl?.includes("mobile")) return <Smartphone size={14} />;
    if (dl?.includes("tablet")) return <Tablet size={14} />;
    return <Monitor size={14} />;
  };

  const deviceColor: Record<string, string> = {
    mobile: "bg-blue-500", desktop: "bg-emerald-500", tablet: "bg-purple-500", other: "bg-stone",
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Análise de Visitantes</h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
              {(["today", "7d", "30d", "90d"] as Period[]).map(p => (
                <button key={p} onClick={() => setPeriod(p)}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${period === p ? "bg-gold text-black" : "text-stone hover:text-cream"}`}>
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
            <button onClick={() => fetchData(period)} className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors">
              <RefreshCw size={16} />
            </button>
            <AdminTopActions />
          </div>
        </div>

        {warn && <div className="rounded-xl bg-yellow-500/10 border border-yellow-500/30 p-3 text-yellow-400 text-sm">{warn}</div>}
        {loading && <div className="flex justify-center py-12"><Loader2 className="animate-spin text-gold" size={28} /></div>}

        {!loading && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
              {[
                { label: "Visitantes Hoje",  value: data.visitors_today.toLocaleString("pt-BR"),       cls: "text-gold" },
                { label: "Online Agora",     value: data.online_visitors.toLocaleString("pt-BR"),       cls: "text-green-400" },
                { label: "Total Sessões",    value: data.total_sessions.toLocaleString("pt-BR"),        cls: "text-blue-400" },
                { label: "Total Eventos",    value: data.total_events.toLocaleString("pt-BR"),          cls: "text-purple-400" },
                { label: "Taxa de Rejeição", value: `${((data.bounce_rate ?? 0) * 100).toFixed(1)}%`,  cls: "text-orange-400" },
                { label: "Tempo Médio",      value: fmtDuration(data.avg_session_duration),             cls: "text-cyan-400" },
              ].map(m => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4">
                  <p className="text-xs text-stone mb-1">{m.label}</p>
                  <p className={`text-xl font-bold ${m.cls}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Sub-tabs */}
            <div className="flex flex-wrap gap-1 bg-surface-02 border border-surface-03 rounded-xl p-1">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button key={id} onClick={() => setTab(id)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${tab === id ? "bg-gold text-black" : "text-stone hover:text-cream hover:bg-surface-03"}`}>
                  <Icon size={13} /> {label}
                </button>
              ))}
            </div>

            {/* ── Visão Geral ── */}
            {tab === "visao_geral" && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2 bg-surface-02 border border-surface-03 rounded-2xl p-5">
                  <h2 className="text-sm font-semibold text-cream mb-4">Visitantes Recentes</h2>
                  {data.recent_visitors?.length ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-stone text-xs border-b border-surface-03">
                            {["Cidade", "Navegador", "Dispositivo", "Sessões", "Pageviews", "Último acesso"].map(h => (
                              <th key={h} className="text-left pb-2 pr-3">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-surface-03">
                          {data.recent_visitors.map(v => (
                            <tr key={v.id} className="hover:bg-surface-03/30 transition-colors">
                              <td className="py-2 pr-3 text-cream">{v.city || "—"}</td>
                              <td className="py-2 pr-3 text-stone text-xs">{v.browser || "—"}</td>
                              <td className="py-2 pr-3">
                                <div className="flex items-center gap-1.5 text-stone">{deviceIcon(v.device)}<span className="text-xs">{v.device || "—"}</span></div>
                              </td>
                              <td className="py-2 pr-3 text-right text-cream">{v.sessions}</td>
                              <td className="py-2 pr-3 text-right text-cream">{v.pageviews}</td>
                              <td className="py-2 text-stone text-xs">{v.last_seen ? new Date(v.last_seen).toLocaleString("pt-BR") : "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <p className="text-stone text-sm text-center py-8">Nenhum visitante registrado.</p>}
                </div>
                <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                  <h2 className="text-sm font-semibold text-cream mb-4">Eventos Mais Comuns</h2>
                  {data.common_events?.length ? (
                    <div className="space-y-3">
                      {data.common_events.map(ev => (
                        <div key={ev.name} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-stone">{ev.name}</span>
                            <span className="text-cream font-medium">{ev.count.toLocaleString("pt-BR")}</span>
                          </div>
                          <div className="h-1.5 bg-surface-03 rounded-full overflow-hidden">
                            <div className="h-full bg-gold rounded-full" style={{ width: `${(ev.count / maxEvent) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-stone text-sm text-center py-8">Sem eventos.</p>}
                </div>
              </div>
            )}

            {/* ── UTMs ── */}
            {tab === "utms" && (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-4">Análise de UTMs</h2>
                {(data.utm_breakdown ?? []).length === 0 ? (
                  <p className="text-stone text-sm text-center py-8">Nenhum dado de UTM registrado.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03">
                          {["Fonte", "Meio", "Campanha", "Sessões", "Conversões", "Taxa Conv."].map(h => (
                            <th key={h} className="text-left pb-2 pr-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {(data.utm_breakdown ?? []).map((u, i) => (
                          <tr key={i} className="hover:bg-surface-03/30 transition-colors">
                            <td className="py-2 pr-3 text-cream font-medium">{u.source || "—"}</td>
                            <td className="py-2 pr-3 text-stone text-xs">{u.medium || "—"}</td>
                            <td className="py-2 pr-3 text-stone text-xs">{u.campaign || "—"}</td>
                            <td className="py-2 pr-3">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-1.5 bg-surface-03 rounded-full overflow-hidden">
                                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(u.sessions / maxUtm) * 100}%` }} />
                                </div>
                                <span className="text-cream text-xs w-10 text-right">{u.sessions}</span>
                              </div>
                            </td>
                            <td className="py-2 pr-3 text-green-400 font-medium">{u.conversions}</td>
                            <td className="py-2 text-stone text-xs">
                              {u.sessions > 0 ? `${((u.conversions / u.sessions) * 100).toFixed(1)}%` : "0%"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* ── Dispositivos ── */}
            {tab === "dispositivos" && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                  <h2 className="text-sm font-semibold text-cream mb-4">Distribuição por Dispositivo</h2>
                  {(data.devices ?? []).length === 0 ? (
                    <p className="text-stone text-sm text-center py-8">Sem dados.</p>
                  ) : (
                    <div className="space-y-4">
                      {(data.devices ?? []).map(d => {
                        const key = d.device_type?.toLowerCase() ?? "other";
                        const bg = deviceColor[key] ?? deviceColor.other;
                        return (
                          <div key={d.device_type} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <div className="flex items-center gap-2 text-cream">
                                {deviceIcon(d.device_type)} {d.device_type}
                              </div>
                              <span className="text-stone">{d.count.toLocaleString("pt-BR")} ({d.pct.toFixed(1)}%)</span>
                            </div>
                            <div className="h-3 bg-surface-03 rounded-full overflow-hidden">
                              <div className={`h-full ${bg} rounded-full`} style={{ width: `${d.pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                  <h2 className="text-sm font-semibold text-cream mb-4">Bônus: Eventos por Dispositivo</h2>
                  <p className="text-stone text-xs">Dados de segmentação de eventos por dispositivo aparecerão aqui conforme o SDK de analytics for configurado.</p>
                </div>
              </div>
            )}

            {/* ── Top Produtos ── */}
            {tab === "produtos" && (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-4">Produtos Mais Visualizados</h2>
                {(data.top_products ?? []).length === 0 ? (
                  <p className="text-stone text-sm text-center py-8">Sem dados de produtos visualizados.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03">
                          {["Produto", "Visualizações", "Adicionou ao Carrinho", "Pedidos", "Conv. Carrinho→Pedido"].map(h => (
                            <th key={h} className="text-left pb-2 pr-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {(data.top_products ?? []).map((p, i) => (
                          <tr key={i} className="hover:bg-surface-03/30 transition-colors">
                            <td className="py-2 pr-3 text-cream font-medium">{p.product_name}</td>
                            <td className="py-2 pr-3 text-stone">{p.views.toLocaleString("pt-BR")}</td>
                            <td className="py-2 pr-3 text-yellow-400">{p.add_to_cart.toLocaleString("pt-BR")}</td>
                            <td className="py-2 pr-3 text-green-400">{p.orders.toLocaleString("pt-BR")}</td>
                            <td className="py-2 text-stone text-xs">
                              {p.add_to_cart > 0 ? `${((p.orders / p.add_to_cart) * 100).toFixed(1)}%` : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* ── Funil ── */}
            {tab === "funil" && (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-6">Funil de Conversão</h2>
                <div className="space-y-4">
                  {(data.funnel ?? EMPTY.funnel!).map((step, i) => {
                    const prev = i > 0 ? (data.funnel ?? EMPTY.funnel!)[i - 1].value : step.value;
                    const dropPct = prev > 0 && i > 0 ? (((prev - step.value) / prev) * 100).toFixed(1) : null;
                    return (
                      <div key={step.label} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded-full bg-surface-03 text-stone flex items-center justify-center text-xs font-bold">{i + 1}</span>
                            <span className="text-cream font-medium">{step.label}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            {dropPct !== null && (
                              <span className="text-red-400 text-xs">-{dropPct}%</span>
                            )}
                            <span className="text-cream font-semibold">{step.value.toLocaleString("pt-BR")}</span>
                          </div>
                        </div>
                        <div className="h-8 bg-surface-03 rounded-xl overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-gold to-gold/60 rounded-xl flex items-center px-3 transition-all duration-700"
                            style={{ width: `${Math.max((step.value / maxFunnel) * 100, step.value > 0 ? 2 : 0)}%` }}>
                            {step.value > 0 && (
                              <span className="text-xs font-bold text-black/80">
                                {maxFunnel > 0 ? `${((step.value / maxFunnel) * 100).toFixed(0)}%` : ""}
                              </span>
                            )}
                          </div>
                        </div>
                        {i < (data.funnel ?? EMPTY.funnel!).length - 1 && (
                          <div className="flex justify-center py-0.5">
                            <ArrowRight size={12} className="text-stone rotate-90" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
