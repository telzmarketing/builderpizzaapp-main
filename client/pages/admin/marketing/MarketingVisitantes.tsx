import { useEffect } from "react";
import { useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowRight,
  Loader2,
  MapPin,
  Monitor,
  RefreshCw,
  ShoppingCart,
  Smartphone,
  Tablet,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import { marketingVisitorsApi, type MarketingVisitorData, type MarketingVisitorsPeriod } from "@/lib/api";

type Period = MarketingVisitorsPeriod;

interface Visitor {
  id: string;
  city: string;
  neighborhood?: string | null;
  browser: string;
  device: string;
  sessions: number;
  pageviews: number;
  last_seen: string;
  status?: "online" | "offline";
  is_online?: boolean;
  latitude?: number | null;
  longitude?: number | null;
  location_accuracy_m?: number | null;
  location_captured_at?: string | null;
}

interface CommonEvent { name: string; count: number; }
interface UtmRow { source: string; medium: string | null; campaign: string | null; sessions: number; conversions: number; }
interface DeviceBreak { device_type: string; count: number; pct: number; }
interface TopProduct { product_name: string; views: number; add_to_cart: number; orders: number; }
interface FunnelStep { label: string; value: number; }

const EMPTY: MarketingVisitorData = {
  visitors_today: 0,
  online_visitors: 0,
  total_sessions: 0,
  total_events: 0,
  bounce_rate: 0,
  avg_session_duration: 0,
  recent_visitors: [],
  common_events: [],
  utm_breakdown: [],
  devices: [],
  top_products: [],
  funnel: [
    { label: "Visitantes", value: 0 },
    { label: "Produtos vistos", value: 0 },
    { label: "Carrinho", value: 0 },
    { label: "Checkout", value: 0 },
    { label: "Pedido finalizado", value: 0 },
  ],
};

const PERIOD_LABELS: Record<Period, string> = {
  today: "Hoje",
  "7d": "7 dias",
  "30d": "30 dias",
  "90d": "90 dias",
};

function fmtDuration(seconds?: number) {
  if (!seconds) return "-";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function Section({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`bg-surface-02 border border-surface-03 rounded-2xl p-5 ${className}`}>
      <h2 className="text-sm font-semibold text-cream mb-4">{title}</h2>
      {children}
    </section>
  );
}

function EmptyState({ label }: { label: string }) {
  return <p className="text-stone text-sm text-center py-8">{label}</p>;
}

export default function MarketingVisitantes() {
  const [period, setPeriod] = useState<Period>("7d");
  const [data, setData] = useState<MarketingVisitorData>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [warn, setWarn] = useState("");

  const recentVisitors = (data.recent_visitors ?? []) as Visitor[];
  const commonEvents = (data.common_events ?? []) as CommonEvent[];
  const utmBreakdown = (data.utm_breakdown ?? []) as UtmRow[];
  const devices = (data.devices ?? []) as DeviceBreak[];
  const topProducts = (data.top_products ?? []) as TopProduct[];
  const funnel = ((data.funnel ?? EMPTY.funnel) as FunnelStep[]) ?? [];

  const onlineCount = recentVisitors.filter((v) => v.is_online).length;
  const offlineCount = Math.max(recentVisitors.length - onlineCount, 0);
  const maxEvent = Math.max(...commonEvents.map((e) => e.count), 1);
  const maxUtm = Math.max(...utmBreakdown.map((u) => u.sessions), 1);
  const maxProductViews = Math.max(...topProducts.map((p) => p.views), 1);
  const maxFunnel = Math.max(...funnel.map((f) => f.value), 1);

  const fetchData = (p: Period, silent = false) => {
    if (!silent) setLoading(true);
    if (!silent) setWarn("");
    marketingVisitorsApi.list(p)
      .then((d) => setData({ ...EMPTY, ...d }))
      .catch(() => {
        if (!silent) setWarn("Nao foi possivel carregar dados de visitantes.");
      })
      .finally(() => {
        if (!silent) setLoading(false);
      });
  };

  useEffect(() => {
    fetchData(period);
    const timer = window.setInterval(() => fetchData(period, true), 15000);
    return () => window.clearInterval(timer);
  }, [period]); // eslint-disable-line

  const deviceIcon = (d: string) => {
    const dl = d?.toLowerCase();
    if (dl?.includes("mobile")) return <Smartphone size={14} />;
    if (dl?.includes("tablet")) return <Tablet size={14} />;
    return <Monitor size={14} />;
  };

  const deviceColor: Record<string, string> = {
    mobile: "bg-blue-500",
    desktop: "bg-emerald-500",
    tablet: "bg-purple-500",
    other: "bg-stone",
  };

  const mapsUrl = (v: Visitor) =>
    v.latitude != null && v.longitude != null
      ? `https://www.google.com/maps?q=${v.latitude},${v.longitude}`
      : "";

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Analise de Visitantes</h1>
            <p className="text-sm text-stone mt-1">Origem, comportamento e presenca na loja.</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
              {(["today", "7d", "30d", "90d"] as Period[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${period === p ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
                >
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
            <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
              {[
                { label: "Visitantes Hoje", value: data.visitors_today.toLocaleString("pt-BR"), cls: "text-gold" },
                { label: "Online Agora", value: data.online_visitors.toLocaleString("pt-BR"), cls: "text-green-400" },
                { label: "Total Sessoes", value: data.total_sessions.toLocaleString("pt-BR"), cls: "text-blue-400" },
                { label: "Total Eventos", value: data.total_events.toLocaleString("pt-BR"), cls: "text-purple-400" },
                { label: "Taxa de Rejeicao", value: `${((data.bounce_rate ?? 0) * 100).toFixed(1)}%`, cls: "text-orange-400" },
                { label: "Tempo Medio", value: fmtDuration(data.avg_session_duration), cls: "text-cyan-400" },
              ].map((m) => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4">
                  <p className="text-xs text-stone mb-1">{m.label}</p>
                  <p className={`text-xl font-bold ${m.cls}`}>{m.value}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <Section title="Visitantes Recentes" className="xl:col-span-2">
                {recentVisitors.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03">
                          {["Status", "Cidade", "Bairro", "Localizacao", "Navegador", "Dispositivo", "Sessoes", "Pageviews", "Ultimo acesso"].map((h) => (
                            <th key={h} className="text-left pb-2 pr-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {recentVisitors.map((v) => (
                          <tr key={v.id} className="hover:bg-surface-03/30 transition-colors">
                            <td className="py-2 pr-3">
                              <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                                v.is_online ? "bg-green-500/15 text-green-300" : "bg-stone/10 text-stone"
                              }`}>
                                <span className={`h-1.5 w-1.5 rounded-full ${v.is_online ? "bg-green-400" : "bg-stone"}`} />
                                {v.is_online ? "Online" : "Offline"}
                              </span>
                            </td>
                            <td className="py-2 pr-3 text-cream">{v.city || "-"}</td>
                            <td className="py-2 pr-3 text-cream">{v.neighborhood || "-"}</td>
                            <td className="py-2 pr-3 text-xs">
                              {mapsUrl(v) ? (
                                <a href={mapsUrl(v)} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-gold hover:underline">
                                  <MapPin size={13} />
                                  {v.latitude?.toFixed(5)}, {v.longitude?.toFixed(5)}
                                </a>
                              ) : (
                                <span className="text-stone">Sem permissao</span>
                              )}
                            </td>
                            <td className="py-2 pr-3 text-stone text-xs">{v.browser || "-"}</td>
                            <td className="py-2 pr-3">
                              <div className="flex items-center gap-1.5 text-stone">{deviceIcon(v.device)}<span className="text-xs">{v.device || "-"}</span></div>
                            </td>
                            <td className="py-2 pr-3 text-right text-cream">{v.sessions}</td>
                            <td className="py-2 pr-3 text-right text-cream">{v.pageviews}</td>
                            <td className="py-2 text-stone text-xs">{v.last_seen ? new Date(v.last_seen).toLocaleString("pt-BR") : "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <EmptyState label="Nenhum visitante registrado." />}
              </Section>

              <Section title="Eventos Mais Comuns">
                {commonEvents.length ? (
                  <div className="space-y-4">
                    {commonEvents.map((ev) => (
                      <div key={ev.name} className="space-y-1.5">
                        <div className="flex justify-between text-xs">
                          <span className="text-stone">{ev.name}</span>
                          <span className="text-cream font-semibold">{ev.count.toLocaleString("pt-BR")}</span>
                        </div>
                        <div className="h-3 bg-surface-03 rounded-full overflow-hidden">
                          <div className="h-full bg-gold rounded-full" style={{ width: `${(ev.count / maxEvent) * 100}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState label="Sem eventos." />}
              </Section>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Section title="Online x Offline">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-green-500/20 bg-green-500/10 p-4">
                    <p className="text-xs text-green-300">Online</p>
                    <p className="text-3xl font-bold text-green-300 mt-1">{onlineCount}</p>
                  </div>
                  <div className="rounded-xl border border-surface-03 bg-surface-03/40 p-4">
                    <p className="text-xs text-stone">Offline</p>
                    <p className="text-3xl font-bold text-stone mt-1">{offlineCount}</p>
                  </div>
                </div>
                <div className="mt-4 h-3 bg-surface-03 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full"
                    style={{ width: `${recentVisitors.length ? (onlineCount / recentVisitors.length) * 100 : 0}%` }}
                  />
                </div>
              </Section>

              <Section title="Dispositivos">
                {devices.length ? (
                  <div className="space-y-4">
                    {devices.map((d) => {
                      const key = d.device_type?.toLowerCase() ?? "other";
                      const bg = deviceColor[key] ?? deviceColor.other;
                      return (
                        <div key={d.device_type} className="space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2 text-cream">{deviceIcon(d.device_type)} {d.device_type}</div>
                            <span className="text-stone">{d.count.toLocaleString("pt-BR")} ({d.pct.toFixed(1)}%)</span>
                          </div>
                          <div className="h-3 bg-surface-03 rounded-full overflow-hidden">
                            <div className={`h-full ${bg} rounded-full`} style={{ width: `${d.pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : <EmptyState label="Sem dados de dispositivo." />}
              </Section>

              <Section title="Funil de Conversao">
                <div className="space-y-4">
                  {funnel.map((step, i) => {
                    const prev = i > 0 ? funnel[i - 1].value : step.value;
                    const dropPct = prev > 0 && i > 0 ? (((prev - step.value) / prev) * 100).toFixed(1) : null;
                    return (
                      <div key={step.label} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2 text-cream">
                            <span className="w-5 h-5 rounded-full bg-surface-03 text-stone flex items-center justify-center text-xs font-bold">{i + 1}</span>
                            {step.label}
                          </div>
                          <div className="flex items-center gap-2">
                            {dropPct !== null && <span className="text-red-400">-{dropPct}%</span>}
                            <span className="text-cream font-semibold">{step.value.toLocaleString("pt-BR")}</span>
                          </div>
                        </div>
                        <div className="h-4 bg-surface-03 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-gold to-gold/60 rounded-full" style={{ width: `${Math.max((step.value / maxFunnel) * 100, step.value > 0 ? 4 : 0)}%` }} />
                        </div>
                        {i < funnel.length - 1 && <ArrowRight size={12} className="text-stone rotate-90 mx-auto" />}
                      </div>
                    );
                  })}
                </div>
              </Section>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <Section title="UTMs">
                {utmBreakdown.length ? (
                  <div className="space-y-3">
                    {utmBreakdown.map((u, i) => (
                      <div key={`${u.source}-${u.medium}-${u.campaign}-${i}`} className="rounded-xl border border-surface-03 bg-surface-03/25 p-3">
                        <div className="flex items-start justify-between gap-3 text-xs">
                          <div>
                            <p className="text-cream font-semibold">{u.source || "direto"}</p>
                            <p className="text-stone mt-0.5">{u.medium || "-"} / {u.campaign || "-"}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-cream font-semibold">{u.sessions} sessoes</p>
                            <p className="text-green-400">{u.conversions} conversoes</p>
                          </div>
                        </div>
                        <div className="h-2 bg-surface-02 rounded-full overflow-hidden mt-3">
                          <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(u.sessions / maxUtm) * 100}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState label="Nenhum dado de UTM registrado." />}
              </Section>

              <Section title="Top Produtos">
                {topProducts.length ? (
                  <div className="space-y-4">
                    {topProducts.map((p, i) => (
                      <div key={`${p.product_name}-${i}`} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <div className="flex min-w-0 items-center gap-2 text-cream">
                            <ShoppingCart size={14} className="text-gold shrink-0" />
                            <span className="truncate font-medium">{p.product_name}</span>
                          </div>
                          <span className="text-stone shrink-0">{p.views} views</span>
                        </div>
                        <div className="h-3 bg-surface-03 rounded-full overflow-hidden">
                          <div className="h-full bg-gold rounded-full" style={{ width: `${(p.views / maxProductViews) * 100}%` }} />
                        </div>
                        <div className="flex items-center gap-4 text-[11px] text-stone">
                          <span>{p.add_to_cart} carrinhos</span>
                          <span>{p.orders} pedidos</span>
                          <span>{p.add_to_cart > 0 ? `${((p.orders / p.add_to_cart) * 100).toFixed(1)}% conv.` : "- conv."}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <EmptyState label="Sem dados de produtos visualizados." />}
              </Section>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
