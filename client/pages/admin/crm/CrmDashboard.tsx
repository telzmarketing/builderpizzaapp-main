import { useEffect, useState } from "react";
import { Loader2, Users, KanbanSquare, ClipboardList, FolderOpen, RefreshCw } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

interface FunnelStage {
  name: string;
  count: number;
  color?: string;
}

interface CrmDashboardData {
  total_clients: number;
  pipeline_cards: number;
  pending_tasks: number;
  groups: number;
  funnel: FunnelStage[];
}

const STAGE_COLORS = [
  "bg-blue-500",
  "bg-purple-500",
  "bg-gold",
  "bg-orange-500",
  "bg-green-500",
];

export default function CrmDashboard() {
  const [data, setData] = useState<CrmDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchData = () => {
    const token = localStorage.getItem("admin_token");
    setLoading(true);
    setError("");
    fetch(`${BASE}/crm/dashboard`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar dashboard CRM."); return r.json(); })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  const maxFunnel = data?.funnel?.length
    ? Math.max(...data.funnel.map((s) => s.count), 1)
    : 1;

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">CRM</p>
            <h1 className="text-2xl font-bold text-cream">Dashboard CRM</h1>
          </div>
          <button
            onClick={fetchData}
            className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors"
          >
            <RefreshCw size={16} />
          </button>
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
            {/* Metric cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: "Total Clientes", value: data.total_clients.toLocaleString("pt-BR"), icon: Users, color: "text-gold", bg: "bg-gold/10" },
                { label: "Cards no Pipeline", value: data.pipeline_cards.toLocaleString("pt-BR"), icon: KanbanSquare, color: "text-blue-400", bg: "bg-blue-500/10" },
                { label: "Tarefas Pendentes", value: data.pending_tasks.toLocaleString("pt-BR"), icon: ClipboardList, color: "text-orange-400", bg: "bg-orange-500/10" },
                { label: "Grupos", value: data.groups.toLocaleString("pt-BR"), icon: FolderOpen, color: "text-purple-400", bg: "bg-purple-500/10" },
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

            {/* Delivery funnel */}
            <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
              <h2 className="text-sm font-semibold text-cream mb-5">Funil Delivery</h2>
              {data.funnel?.length ? (
                <div className="space-y-3">
                  {data.funnel.map((stage, i) => (
                    <div key={stage.name} className="flex items-center gap-4">
                      <div className="w-36 text-xs text-stone truncate text-right shrink-0">
                        {stage.name}
                      </div>
                      <div className="flex-1 flex items-center gap-3">
                        <div className="flex-1 h-7 bg-surface-03 rounded-xl overflow-hidden">
                          <div
                            className={`h-full rounded-xl ${STAGE_COLORS[i % STAGE_COLORS.length]} transition-all duration-500 flex items-center px-3`}
                            style={{ width: `${Math.max((stage.count / maxFunnel) * 100, 4)}%` }}
                          >
                            {stage.count > 0 && (
                              <span className="text-xs font-bold text-white/90">
                                {stage.count}
                              </span>
                            )}
                          </div>
                        </div>
                        <span className="text-xs text-stone w-8 text-right shrink-0">{stage.count}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-stone text-sm text-center py-8">Sem dados de funil disponíveis.</p>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
