import { type ElementType, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  Brain,
  CheckCircle2,
  Clock,
  Loader2,
  RefreshCw,
  Sparkles,
  Tag,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";
import { crmApi, type ApiCRMAnalysisStatus } from "@/lib/api";

function segmentLabel(segment: string) {
  const labels: Record<string, string> = {
    lead: "Lead",
    novo_comprador: "Novo comprador",
    recorrente: "Recorrente",
    vip: "VIP",
    alto_ticket: "Alto ticket",
    em_risco: "Em risco",
    inativo: "Inativo",
  };
  return labels[segment] ?? segment.replace("_", " ");
}

function riskBadge(risk: string) {
  const map: Record<string, string> = {
    low: "bg-green-500/15 text-green-300",
    medium: "bg-yellow-500/15 text-yellow-300",
    high: "bg-red-500/15 text-red-300",
  };
  return map[risk] ?? "bg-surface-03 text-stone";
}

function confidenceLabel(confidence: string) {
  const labels: Record<string, string> = { high: "Alta", medium: "Media", low: "Baixa" };
  return labels[confidence] ?? confidence;
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string | number;
  icon: ElementType;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-02 p-4">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2 ${tone}`}>
          <Icon size={18} />
        </div>
        <div>
          <p className="text-xs text-stone">{label}</p>
          <p className="text-xl font-bold text-cream">{value}</p>
        </div>
      </div>
    </div>
  );
}

export default function CrmInteligencia() {
  const [data, setData] = useState<ApiCRMAnalysisStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const status = await crmApi.getAnalysisStatus(150);
      setData(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar inteligencia de clientes.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    const status = data?.job?.status;
    if (status !== "pending" && status !== "running") return;
    const timer = window.setInterval(() => {
      load();
    }, 3500);
    return () => window.clearInterval(timer);
  }, [data?.job?.status]);

  const startAnalysis = async () => {
    setRunning(true);
    setError(null);
    try {
      await crmApi.analyzeAllCustomers();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao iniciar analise em massa.");
    } finally {
      setRunning(false);
    }
  };

  const job = data?.job;
  const isProcessing = job?.status === "pending" || job?.status === "running";
  const progress = useMemo(() => {
    if (!job?.total_customers) return 0;
    return Math.min(100, Math.round((job.processed_customers / job.total_customers) * 100));
  }, [job]);

  if (loading) {
    return (
      <main className="min-h-screen bg-brand-dark p-6">
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="animate-spin text-gold" size={30} />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-brand-dark p-4 md:p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-gold">CRM</p>
            <h1 className="text-2xl font-bold text-cream">Inteligencia de Clientes</h1>
            <p className="text-sm text-stone">Analise em massa, segmentos inteligentes e proximas acoes.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={load}
              className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-medium text-stone transition hover:text-cream"
            >
              <RefreshCw size={15} /> Atualizar
            </button>
            <button
              type="button"
              onClick={startAnalysis}
              disabled={running || isProcessing}
              className="inline-flex items-center gap-2 rounded-lg bg-gold px-4 py-2 text-sm font-semibold text-brand-dark transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {running || isProcessing ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
              Analisar todos os clientes
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {job && (
          <section className="rounded-xl border border-surface-03 bg-surface-02 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-gold/10 p-2 text-gold">
                  <Clock size={18} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-cream">Ultima analise</p>
                  <p className="text-xs text-stone">
                    {job.created_at ? new Date(job.created_at).toLocaleString("pt-BR") : "Sem data"} - {job.status}
                  </p>
                </div>
              </div>
              <div className="w-full md:max-w-sm">
                <div className="mb-1 flex justify-between text-xs text-stone">
                  <span>{job.processed_customers} de {job.total_customers}</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-surface-03">
                  <div className="h-full rounded-full bg-gold" style={{ width: `${progress}%` }} />
                </div>
              </div>
            </div>
            {job.error_message && <p className="mt-2 text-xs text-red-300">{job.error_message}</p>}
          </section>
        )}

        <section className="grid gap-3 md:grid-cols-4">
          <StatCard label="Total analisado" value={data?.summary.total_analyzed ?? 0} icon={Brain} tone="bg-gold/10 text-gold" />
          <StatCard label="Tags sugeridas" value={data?.summary.tags_suggested ?? 0} icon={Tag} tone="bg-orange-500/10 text-orange-300" />
          <StatCard label="Grupos sugeridos" value={data?.summary.groups_suggested ?? 0} icon={Users} tone="bg-blue-500/10 text-blue-300" />
          <StatCard label="Alta recompra" value={data?.summary.high_repurchase_customers ?? 0} icon={TrendingUp} tone="bg-green-500/10 text-green-300" />
          <StatCard label="Clientes VIP" value={data?.summary.vip_customers ?? 0} icon={UserCheck} tone="bg-purple-500/10 text-purple-300" />
          <StatCard label="Clientes inativos" value={data?.summary.inactive_customers ?? 0} icon={AlertCircle} tone="bg-red-500/10 text-red-300" />
          <StatCard label="Clientes em risco" value={data?.summary.risk_customers ?? 0} icon={AlertCircle} tone="bg-yellow-500/10 text-yellow-300" />
          <StatCard label="Base listada" value={data?.customers.length ?? 0} icon={CheckCircle2} tone="bg-surface-03 text-stone" />
        </section>

        <section className="overflow-hidden rounded-xl border border-surface-03 bg-surface-02">
          <div className="border-b border-surface-03 px-4 py-3">
            <h2 className="font-semibold text-cream">Clientes analisados</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-surface-01 text-xs uppercase text-stone">
                <tr>
                  <th className="px-4 py-3">Cliente</th>
                  <th className="px-4 py-3">Segmento</th>
                  <th className="px-4 py-3">Tags sugeridas</th>
                  <th className="px-4 py-3">Grupos sugeridos</th>
                  <th className="px-4 py-3">Risco</th>
                  <th className="px-4 py-3">Confianca</th>
                  <th className="px-4 py-3">Proxima acao</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-03">
                {(data?.customers ?? []).map((customer) => (
                  <tr key={customer.customer_id} className="text-stone transition hover:bg-surface-01/60">
                    <td className="px-4 py-3">
                      <Link to={`/painel/clientes/${customer.customer_id}`} className="font-medium text-cream hover:text-gold">
                        {customer.customer_name}
                      </Link>
                      <p className="text-xs text-stone/70">{customer.phone || customer.email || "Sem contato"}</p>
                    </td>
                    <td className="px-4 py-3 text-cream">{segmentLabel(customer.segment)}</td>
                    <td className="px-4 py-3">{customer.tags_suggested.length ? customer.tags_suggested.join(", ") : "-"}</td>
                    <td className="px-4 py-3">{customer.groups_suggested.length ? customer.groups_suggested.join(", ") : "-"}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-1 text-xs font-medium ${riskBadge(customer.churn_risk)}`}>
                        {customer.churn_risk}
                      </span>
                    </td>
                    <td className="px-4 py-3">{confidenceLabel(customer.confidence)}</td>
                    <td className="max-w-xs px-4 py-3 text-stone/80">{customer.next_best_action || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(data?.customers.length ?? 0) === 0 && (
            <div className="py-12 text-center text-sm text-stone">Nenhum cliente analisado ainda.</div>
          )}
        </section>
      </div>
    </main>
  );
}
