import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  Loader2,
  MessageCircle,
  Package,
  RefreshCw,
  Server,
  ShieldCheck,
  Truck,
  Wallet,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import {
  agenteWhatsAppApi,
  whatsappGatewayApi,
  type ApiAgenteWhatsAppDashboard,
  type ApiAgenteWhatsAppObservability,
  type ApiAgenteWhatsAppOperationalMetrics,
  type ApiWhatsAppGatewayOverview,
} from "@/lib/api";

type DashboardData = {
  agent: ApiAgenteWhatsAppDashboard | null;
  operations: ApiAgenteWhatsAppOperationalMetrics | null;
  observability: ApiAgenteWhatsAppObservability | null;
  gateway: ApiWhatsAppGatewayOverview | null;
};

const emptyData: DashboardData = { agent: null, operations: null, observability: null, gateway: null };

function displayNumber(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : value.toLocaleString("pt-BR");
}

function displayPercent(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

function displayDuration(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  if (value < 60) return `${Math.round(value)}s`;
  return `${Math.floor(value / 60)}min`;
}

function statusLabel(status: string | null | undefined) {
  if (!status) return "Indisponível";
  if (status === "healthy") return "Saudável";
  if (status === "degraded") return "Degradado";
  if (status === "critical") return "Crítico";
  return status;
}

function statusClass(status: string | null | undefined) {
  if (status === "healthy") return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
  if (status === "critical") return "text-red-400 bg-red-500/10 border-red-500/20";
  return "text-amber-300 bg-amber-500/10 border-amber-500/20";
}

function MetricCard({ label, value, detail, icon: Icon }: { label: string; value: string; detail: string; icon: LucideIcon }) {
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-02 p-4 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-stone">{label}</p>
        <span className="rounded-lg bg-gold/10 p-2 text-gold"><Icon size={17} aria-hidden="true" /></span>
      </div>
      <p className="mt-4 text-2xl font-black text-cream">{value}</p>
      <p className="mt-1 text-xs text-stone">{detail}</p>
    </div>
  );
}

const quickLinks = [
  { label: "IA / Agente WhatsApp", description: "Conversas, configurações e operação do agente", path: "/painel/crm/agente-whatsapp", icon: Bot },
  { label: "WhatsApp Gateway", description: "Instâncias, conexão e saúde do gateway", path: "/painel/whatsapp-gateway", icon: Server },
  { label: "Chatbot / Automações", description: "Regras e automações já disponíveis", path: "/painel/chatbot", icon: MessageCircle },
  { label: "BI", description: "Indicadores e análises do negócio", path: "/painel/bi", icon: BarChart3 },
  { label: "Estoque", description: "Saldo, movimentações e custo", path: "/painel/gestao/estoque", icon: Package },
  { label: "Financeiro", description: "Contas e visão financeira", path: "/painel/gestao/financeiro", icon: Wallet },
  { label: "Logística", description: "Entregas e operação de rota", path: "/painel/logistica", icon: Truck },
];

export default function Gestor() {
  const [data, setData] = useState<DashboardData>(emptyData);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    else setLoading(true);
    setError("");
    const results = await Promise.allSettled([
      agenteWhatsAppApi.dashboard(),
      agenteWhatsAppApi.observability(),
      agenteWhatsAppApi.operationalMetrics(),
      whatsappGatewayApi.overview(),
    ]);
    const next: DashboardData = {
      agent: results[0].status === "fulfilled" ? results[0].value : null,
      observability: results[1].status === "fulfilled" ? results[1].value : null,
      operations: results[2].status === "fulfilled" ? results[2].value : null,
      gateway: results[3].status === "fulfilled" ? results[3].value : null,
    };
    setData(next);
    if (results.every((result) => result.status === "rejected")) {
      setError("Não foi possível carregar os indicadores do Gestor IA.");
    } else if (results.some((result) => result.status === "rejected")) {
      setError("Alguns indicadores estão indisponíveis no momento.");
    }
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  const agentStatus = data.observability?.health_status;
  const gatewayStatus = data.gateway?.provider?.runtime_status;
  const hasData = Object.values(data).some(Boolean);
  const lastUpdate = useMemo(() => data.operations?.generated_at, [data.operations?.generated_at]);

  return (
    <div className="space-y-6 pb-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold">Gestão assistida</p>
          <h1 className="mt-1 text-2xl font-black text-cream sm:text-3xl">Gestor IA</h1>
          <p className="mt-2 max-w-2xl text-sm text-stone">Visão operacional baseada nos serviços existentes do ERP. Esta primeira fatia é somente leitura.</p>
        </div>
        <button type="button" onClick={() => void loadDashboard(true)} disabled={loading || refreshing} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-surface-03 bg-surface-02 px-4 text-sm font-bold text-cream transition hover:border-gold/50 disabled:cursor-not-allowed disabled:opacity-60">
          <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} aria-hidden="true" /> Atualizar
        </button>
      </div>

      {error && <div role="alert" className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"><AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-300" />{error}</div>}

      {loading ? (
        <div className="flex min-h-64 items-center justify-center rounded-xl border border-surface-03 bg-surface-02 text-stone"><Loader2 size={30} className="animate-spin text-gold" /><span className="ml-3 text-sm">Carregando indicadores reais...</span></div>
      ) : !hasData ? (
        <div className="rounded-xl border border-surface-03 bg-surface-02 px-6 py-12 text-center"><WifiOff size={30} className="mx-auto text-stone" /><h2 className="mt-3 text-lg font-bold text-cream">Nenhum indicador disponível</h2><p className="mt-2 text-sm text-stone">Verifique a sessão e a disponibilidade dos serviços para tentar novamente.</p></div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Conversas abertas" value={displayNumber(data.agent?.sessions_open)} detail={`${displayNumber(data.agent?.sessions_human)} em atendimento humano`} icon={MessageCircle} />
            <MetricCard label="Mensagens hoje" value={displayNumber(data.agent?.messages_today)} detail={`${displayNumber(data.agent?.inbound_today)} recebidas · ${displayNumber(data.agent?.outbound_today)} enviadas`} icon={Activity} />
            <MetricCard label="Taxa de sucesso" value={displayPercent(data.observability?.success_rate)} detail={`${displayNumber(data.observability?.attempted_deliveries)} tentativas de entrega`} icon={CheckCircle2} />
            <MetricCard label="Atendimentos ativos" value={displayNumber(data.operations?.active_attendances)} detail={`${displayNumber(data.operations?.waiting_response)} aguardando resposta`} icon={Clock3} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <section className="rounded-xl border border-surface-03 bg-surface-02 p-5 shadow-soft">
              <div className="flex items-center justify-between gap-3"><div><h2 className="font-bold text-cream">Saúde dos serviços</h2><p className="mt-1 text-xs text-stone">Estado retornado pelas APIs existentes</p></div><ShieldCheck size={20} className="text-gold" /></div>
              <div className="mt-5 space-y-3">
                <StatusRow label="Agente WhatsApp" status={statusLabel(agentStatus)} detail={data.observability?.health_message} tone={agentStatus} />
                <StatusRow label="WhatsApp Gateway" status={gatewayStatus ? String(gatewayStatus) : "Indisponível"} detail={data.gateway ? `${data.gateway.connected_instances} de ${data.gateway.total_instances} instância(s) conectada(s)` : undefined} tone={data.gateway?.failed_instances ? "critical" : data.gateway ? "healthy" : undefined} />
              </div>
            </section>
            <section className="rounded-xl border border-surface-03 bg-surface-02 p-5 shadow-soft">
              <div className="flex items-center justify-between gap-3"><div><h2 className="font-bold text-cream">Métricas operacionais</h2><p className="mt-1 text-xs text-stone">Sem estimativas quando a API não retorna dados</p></div><Database size={20} className="text-gold" /></div>
              <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <MiniMetric label="Agentes IA" value={displayNumber(data.operations?.active_ai_agents)} />
                <MiniMetric label="Não lidas" value={displayNumber(data.operations?.unread_messages)} />
                <MiniMetric label="Resp. médio" value={displayDuration(data.operations?.avg_response_time_seconds)} />
                <MiniMetric label="Alertas ativos" value={displayNumber(data.observability?.active_alerts)} />
              </div>
              {lastUpdate && <p className="mt-5 text-xs text-stone">Atualizado em {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(lastUpdate))}</p>}
            </section>
          </div>

          <section>
            <div className="mb-3 flex items-center justify-between"><div><h2 className="font-bold text-cream">Acessos rápidos</h2><p className="mt-1 text-xs text-stone">Módulos já existentes no painel administrativo</p></div><ArrowUpRight size={18} className="text-stone" /></div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{quickLinks.map(({ label, description, path, icon: Icon }) => <Link key={path} to={path} className="group rounded-xl border border-surface-03 bg-surface-02 p-4 transition hover:border-gold/50 hover:bg-surface-03"><div className="flex items-start justify-between gap-3"><span className="rounded-lg bg-gold/10 p-2 text-gold"><Icon size={18} aria-hidden="true" /></span><ArrowUpRight size={16} className="text-stone transition group-hover:text-gold" /></div><h3 className="mt-4 text-sm font-bold text-cream">{label}</h3><p className="mt-1 text-xs leading-5 text-stone">{description}</p></Link>)}</div>
          </section>
        </>
      )}
    </div>
  );
}

function StatusRow({ label, status, detail, tone }: { label: string; status: string; detail?: string; tone?: string }) {
  return <div className="flex flex-col gap-2 rounded-lg border border-surface-03 bg-surface-01 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-semibold text-cream">{label}</p><p className="mt-1 text-xs text-stone">{detail || "Sem detalhe retornado"}</p></div><span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-bold ${statusClass(tone)}`}><span className="h-1.5 w-1.5 rounded-full bg-current" />{status}</span></div>;
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs text-stone">{label}</p><p className="mt-1 text-lg font-black text-cream">{value}</p></div>;
}
