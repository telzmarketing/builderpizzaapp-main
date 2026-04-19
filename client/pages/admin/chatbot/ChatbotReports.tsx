import { useEffect, useState } from "react";
import { MessageCircle, Users, Clock, Cpu, TrendingUp, AlertCircle, RefreshCw } from "lucide-react";
import { chatbotAdminApi, type ChatbotAnalytics } from "@/lib/chatbotApi";

function Stat({ label, value, sub, color = "text-gold", icon }: {
  label: string; value: string | number; sub?: string; color?: string; icon: React.ReactNode;
}) {
  return (
    <div className="bg-surface-02 rounded-xl p-5 border border-surface-03">
      <div className="flex items-center gap-2 mb-3">
        <span className={color}>{icon}</span>
        <span className="text-stone text-xs">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-stone text-xs mt-1">{sub}</p>}
    </div>
  );
}

function Bar({ label, value, max, color = "bg-gold" }: { label: string; value: number; max: number; color?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-parchment">{label}</span>
        <span className="text-stone">{value} ({pct}%)</span>
      </div>
      <div className="h-2 bg-surface-03 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function ChatbotReports() {
  const [data, setData] = useState<ChatbotAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshed, setRefreshed] = useState<Date | null>(null);

  const load = () => {
    setLoading(true);
    chatbotAdminApi.analytics()
      .then((d) => { setData(d); setRefreshed(new Date()); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  if (loading && !data) return <div className="text-stone text-center py-16">Carregando...</div>;
  if (!data) return <div className="text-red-400 text-center py-16">Erro ao carregar relatório.</div>;

  const total = data.abertas + data.encerradas + data.em_humano;
  const avgCostPerConv = data.total_mes > 0 ? data.custo_estimado_mes / data.total_mes : 0;

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-cream font-bold text-base">Relatórios & Métricas</h3>
        <div className="flex items-center gap-3">
          {refreshed && <span className="text-stone text-xs">Atualizado {refreshed.toLocaleTimeString("pt-BR")}</span>}
          <button onClick={load} disabled={loading}
            className="flex items-center gap-2 bg-surface-02 hover:bg-surface-03 border border-surface-03 text-parchment text-xs font-medium py-1.5 px-3 rounded-lg transition-colors">
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Atualizar
          </button>
        </div>
      </div>

      {/* Volume */}
      <div>
        <h4 className="text-parchment text-xs font-semibold uppercase tracking-wider mb-3">Volume de conversas</h4>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat icon={<MessageCircle size={18} />} label="Hoje"       value={data.total_hoje}   />
          <Stat icon={<TrendingUp size={18} />}    label="Esta semana" value={data.total_semana} />
          <Stat icon={<Users size={18} />}          label="Este mês"   value={data.total_mes}    />
          <Stat icon={<AlertCircle size={18} />}    label="Aguard. humano" value={data.em_humano}
            color={data.em_humano > 0 ? "text-orange-400" : "text-gold"} />
        </div>
      </div>

      {/* Status breakdown */}
      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-4">
        <h4 className="text-parchment text-xs font-semibold uppercase tracking-wider">Distribuição de status</h4>
        <Bar label="Abertas"    value={data.abertas}    max={total} color="bg-blue-500" />
        <Bar label="Humano"     value={data.em_humano}  max={total} color="bg-orange-500" />
        <Bar label="Encerradas" value={data.encerradas} max={total} color="bg-surface-03" />
        <p className="text-stone text-xs">Total de conversas ativas/históricas: {total}</p>
      </div>

      {/* Performance */}
      <div>
        <h4 className="text-parchment text-xs font-semibold uppercase tracking-wider mb-3">Performance</h4>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <Stat
            icon={<Clock size={18} />}
            label="Tempo médio de resposta"
            value={data.tempo_medio_resposta_ms ? `${(data.tempo_medio_resposta_ms / 1000).toFixed(1)}s` : "—"}
            sub="Latência da IA incluída"
          />
          <Stat
            icon={<Cpu size={18} />}
            label="Tokens este mês"
            value={data.tokens_total_mes.toLocaleString("pt-BR")}
            sub="Entrada + saída"
            color="text-parchment"
          />
          <Stat
            icon={<TrendingUp size={18} />}
            label="Custo estimado/mês"
            value={`$${data.custo_estimado_mes.toFixed(3)}`}
            sub={`~$${avgCostPerConv.toFixed(4)} por conversa`}
            color="text-parchment"
          />
        </div>
      </div>

      {/* Cost detail */}
      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-3">
        <h4 className="text-parchment text-xs font-semibold uppercase tracking-wider">Estimativa de custo</h4>
        <p className="text-stone text-xs">Cálculo baseado em preço médio de $0.003/1K tokens (Claude Haiku). Valores são estimativas.</p>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-surface-03 rounded-lg px-4 py-3 text-center">
            <p className="text-stone text-xs">Por conversa</p>
            <p className="text-cream font-bold mt-1">${avgCostPerConv.toFixed(4)}</p>
          </div>
          <div className="bg-surface-03 rounded-lg px-4 py-3 text-center">
            <p className="text-stone text-xs">Este mês</p>
            <p className="text-cream font-bold mt-1">${data.custo_estimado_mes.toFixed(3)}</p>
          </div>
          <div className="bg-surface-03 rounded-lg px-4 py-3 text-center">
            <p className="text-stone text-xs">Projeção anual</p>
            <p className="text-cream font-bold mt-1">${(data.custo_estimado_mes * 12).toFixed(2)}</p>
          </div>
        </div>
      </div>

      <p className="text-stone text-xs">* Os dados de custo são estimativas baseadas no consumo de tokens registrado. Verifique o painel do provedor para valores exatos.</p>
    </div>
  );
}
