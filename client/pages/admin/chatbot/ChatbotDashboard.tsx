import { useEffect, useState } from "react";
import { MessageCircle, Users, Clock, Cpu, TrendingUp, AlertCircle } from "lucide-react";
import { chatbotAdminApi, type ChatbotAnalytics, type ChatbotConversation } from "@/lib/chatbotApi";

function StatCard({ icon, label, value, sub, color = "text-gold" }: {
  icon: React.ReactNode; label: string; value: string | number;
  sub?: string; color?: string;
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

const STATUS_LABEL: Record<string, string> = { aberta: "Aberta", em_humano: "Humano", encerrada: "Encerrada" };
const STATUS_COLOR: Record<string, string> = {
  aberta:    "bg-blue-500/20 text-blue-400 border-blue-500/30",
  em_humano: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  encerrada: "bg-surface-03 text-stone border-surface-03",
};

export default function ChatbotDashboard() {
  const [analytics, setAnalytics] = useState<ChatbotAnalytics | null>(null);
  const [recent, setRecent] = useState<ChatbotConversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      chatbotAdminApi.analytics(),
      chatbotAdminApi.listConversations(undefined, 1),
    ]).then(([a, list]) => {
      setAnalytics(a);
      setRecent(list.items.slice(0, 8));
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-stone text-center py-16">Carregando...</div>;
  if (!analytics) return <div className="text-red-400 text-center py-16">Erro ao carregar dados.</div>;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Alertas de conversas com humano */}
      {analytics.em_humano > 0 && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl px-5 py-3 flex items-center gap-3">
          <AlertCircle size={18} className="text-orange-400 flex-shrink-0" />
          <p className="text-orange-300 text-sm font-medium">
            {analytics.em_humano} conversa{analytics.em_humano > 1 ? "s" : ""} aguardando atendimento humano
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={<MessageCircle size={18} />} label="Conversas hoje"   value={analytics.total_hoje}   />
        <StatCard icon={<TrendingUp size={18} />}    label="Esta semana"      value={analytics.total_semana} />
        <StatCard icon={<Users size={18} />}          label="Este mês"         value={analytics.total_mes}    />
        <StatCard icon={<AlertCircle size={18} />}    label="Aguard. humano"   value={analytics.em_humano}
          color={analytics.em_humano > 0 ? "text-orange-400" : "text-gold"} />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={<MessageCircle size={18} />} label="Abertas"      value={analytics.abertas}    color="text-blue-400" />
        <StatCard icon={<MessageCircle size={18} />} label="Encerradas"   value={analytics.encerradas} color="text-stone" />
        <StatCard
          icon={<Clock size={18} />}
          label="Resp. média"
          value={analytics.tempo_medio_resposta_ms ? `${(analytics.tempo_medio_resposta_ms / 1000).toFixed(1)}s` : "—"}
        />
        <StatCard
          icon={<Cpu size={18} />}
          label="Custo estimado/mês"
          value={`$${analytics.custo_estimado_mes.toFixed(3)}`}
          sub={`${analytics.tokens_total_mes.toLocaleString()} tokens`}
          color="text-parchment"
        />
      </div>

      {/* Conversas recentes */}
      <div>
        <h3 className="text-cream font-bold mb-3">Conversas recentes</h3>
        {recent.length === 0 ? (
          <p className="text-stone text-sm text-center py-8">Nenhuma conversa ainda.</p>
        ) : (
          <div className="space-y-2">
            {recent.map((c) => (
              <div key={c.id} className="bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLOR[c.status]}`}>
                  {STATUS_LABEL[c.status]}
                </span>
                <span className="text-stone text-xs">{c.pagina_origem || "/"}</span>
                {c.intencao_detectada && (
                  <span className="text-parchment text-xs bg-surface-03 px-2 py-0.5 rounded-full">{c.intencao_detectada}</span>
                )}
                <span className="ml-auto text-stone text-xs">
                  {new Date(c.iniciada_em).toLocaleString("pt-BR")}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
