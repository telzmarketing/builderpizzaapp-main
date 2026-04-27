import { useEffect, useState } from "react";
import { Loader2, Users, Monitor, Smartphone, RefreshCw, Globe } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

type Period = "today" | "7d" | "30d";

interface Visitor {
  id: string;
  city: string;
  browser: string;
  device: string;
  sessions: number;
  pageviews: number;
  last_seen: string;
}

interface CommonEvent {
  name: string;
  count: number;
}

interface VisitorData {
  visitors_today: number;
  online_visitors: number;
  total_sessions: number;
  total_events: number;
  recent_visitors: Visitor[];
  common_events: CommonEvent[];
}

const PERIOD_LABELS: Record<Period, string> = {
  today: "Hoje",
  "7d": "7 dias",
  "30d": "30 dias",
};

export default function MarketingVisitantes() {
  const [period, setPeriod] = useState<Period>("7d");
  const [data, setData] = useState<VisitorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchData = (p: Period) => {
    const token = localStorage.getItem("admin_token");
    setLoading(true);
    setError("");
    fetch(`${BASE}/marketing/visitors?period=${p}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar visitantes."); return r.json(); })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(period); }, [period]);

  const deviceIcon = (device: string) =>
    device?.toLowerCase().includes("mobile") ? (
      <Smartphone size={14} className="text-stone" />
    ) : (
      <Monitor size={14} className="text-stone" />
    );

  const maxEvent = data?.common_events?.length
    ? Math.max(...data.common_events.map((e) => e.count), 1)
    : 1;

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
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
              {(["today", "7d", "30d"] as Period[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${period === p ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
            <button
              onClick={() => fetchData(period)}
              className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}
        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>
        )}

        {!loading && !error && data && (
          <>
            {/* Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: "Visitantes Hoje", value: data.visitors_today.toLocaleString("pt-BR"), icon: Users, color: "text-gold", bg: "bg-gold/10" },
                { label: "Online Agora", value: data.online_visitors.toLocaleString("pt-BR"), icon: Globe, color: "text-green-400", bg: "bg-green-500/10" },
                { label: "Total Sessões", value: data.total_sessions.toLocaleString("pt-BR"), icon: Monitor, color: "text-blue-400", bg: "bg-blue-500/10" },
                { label: "Total Eventos", value: data.total_events.toLocaleString("pt-BR"), icon: Smartphone, color: "text-purple-400", bg: "bg-purple-500/10" },
              ].map((m) => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-stone">{m.label}</span>
                    <div className={`p-1.5 rounded-lg ${m.bg}`}>
                      <m.icon size={14} className={m.color} />
                    </div>
                  </div>
                  <p className={`text-2xl font-bold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Recent visitors */}
              <div className="lg:col-span-2 bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-4">Visitantes Recentes</h2>
                {data.recent_visitors?.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03">
                          <th className="text-left pb-2 pr-3">Cidade</th>
                          <th className="text-left pb-2 pr-3">Navegador</th>
                          <th className="text-left pb-2 pr-3">Dispositivo</th>
                          <th className="text-right pb-2 pr-3">Sessões</th>
                          <th className="text-right pb-2 pr-3">Pageviews</th>
                          <th className="text-left pb-2">Último acesso</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {data.recent_visitors.map((v) => (
                          <tr key={v.id} className="hover:bg-surface-03/30 transition-colors">
                            <td className="py-2 pr-3 text-cream">{v.city || "—"}</td>
                            <td className="py-2 pr-3 text-stone text-xs">{v.browser || "—"}</td>
                            <td className="py-2 pr-3">
                              <div className="flex items-center gap-1.5">
                                {deviceIcon(v.device)}
                                <span className="text-stone text-xs">{v.device || "—"}</span>
                              </div>
                            </td>
                            <td className="py-2 pr-3 text-right text-cream">{v.sessions}</td>
                            <td className="py-2 pr-3 text-right text-cream">{v.pageviews}</td>
                            <td className="py-2 text-stone text-xs">
                              {v.last_seen ? new Date(v.last_seen).toLocaleString("pt-BR") : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-stone text-sm text-center py-8">Nenhum visitante registrado.</p>
                )}
              </div>

              {/* Common events */}
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
                <h2 className="text-sm font-semibold text-cream mb-4">Eventos Mais Comuns</h2>
                {data.common_events?.length ? (
                  <div className="space-y-3">
                    {data.common_events.map((ev) => (
                      <div key={ev.name} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-stone">{ev.name}</span>
                          <span className="text-cream font-medium">{ev.count.toLocaleString("pt-BR")}</span>
                        </div>
                        <div className="h-1.5 bg-surface-03 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gold rounded-full transition-all duration-500"
                            style={{ width: `${(ev.count / maxEvent) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-stone text-sm text-center py-8">Sem eventos registrados.</p>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
