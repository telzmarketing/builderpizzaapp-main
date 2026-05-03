import { useEffect, useMemo, useState, type ElementType, type ReactNode } from "react";
import {
  AlertTriangle,
  BarChart3,
  Brain,
  DollarSign,
  Loader2,
  Package,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  biApi,
  type ApiBIDashboard,
  type ApiBIInsight,
  type ApiBIKpi,
  type ApiBIPeriod,
  type ApiBIRecommendation,
} from "@/lib/api";

const PERIODS: Array<{ key: ApiBIPeriod; label: string }> = [
  { key: "today", label: "Hoje" },
  { key: "7d", label: "7 dias" },
  { key: "30d", label: "30 dias" },
  { key: "90d", label: "90 dias" },
  { key: "month", label: "Mes atual" },
];

const KPI_ICONS: Record<string, ElementType> = {
  revenue: DollarSign,
  orders: BarChart3,
  average_ticket: Target,
  new_customers: Users,
  recurring_customers: Users,
  cancelled_orders: AlertTriangle,
  payment_problems: AlertTriangle,
  delayed_deliveries: AlertTriangle,
  discounts: Sparkles,
  loyalty_points: Brain,
};

const IMPACT_CLASS: Record<ApiBIInsight["impact_level"], string> = {
  critical: "border-red-500/50 bg-red-500/10 text-red-200",
  high: "border-red-500/35 bg-red-500/10 text-red-200",
  medium: "border-gold/40 bg-gold/10 text-gold",
  low: "border-surface-03 bg-surface-02 text-stone",
};

function money(value: number) {
  return (value ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function number(value: number) {
  return (value ?? 0).toLocaleString("pt-BR");
}

function formatKpi(kpi: ApiBIKpi) {
  if (kpi.unit === "currency") return money(kpi.value);
  if (kpi.unit === "percent") return `${(kpi.value ?? 0).toFixed(1)}%`;
  return number(kpi.value);
}

function KpiCard({ kpi }: { kpi: ApiBIKpi }) {
  const Icon = KPI_ICONS[kpi.key] ?? BarChart3;
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-02 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-stone">{kpi.label}</p>
          <p className="mt-2 text-2xl font-bold text-cream">{formatKpi(kpi)}</p>
        </div>
        <span className="rounded-lg bg-gold/10 p-2 text-gold">
          <Icon size={18} />
        </span>
      </div>
      {kpi.helper && <p className="mt-3 line-clamp-2 text-xs text-stone">{kpi.helper}</p>}
    </div>
  );
}

function Section({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-bold text-cream">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-surface-03 bg-surface-02 p-6 text-center text-sm text-stone">
      {label}
    </div>
  );
}

function ImpactBadge({ impact }: { impact: ApiBIInsight["impact_level"] }) {
  const label: Record<ApiBIInsight["impact_level"], string> = {
    critical: "Critico",
    high: "Alto",
    medium: "Medio",
    low: "Baixo",
  };
  return (
    <span className={`rounded-full border px-2 py-1 text-[11px] font-bold uppercase ${IMPACT_CLASS[impact]}`}>
      {label[impact]}
    </span>
  );
}

function InsightCard({ item }: { item: ApiBIInsight }) {
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-02 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-cream">{item.title}</p>
          <p className="mt-2 text-sm text-stone">{item.description}</p>
        </div>
        <ImpactBadge impact={item.impact_level} />
      </div>
      <p className="mt-4 rounded-lg border border-surface-03 bg-surface-01 p-3 text-sm text-cream">
        {item.recommendation}
      </p>
    </div>
  );
}

function RecommendationCard({
  item,
  onStatus,
}: {
  item: ApiBIRecommendation;
  onStatus: (insightId: string, status: "resolved" | "ignored" | "postponed") => void;
}) {
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-02 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-cream">{item.title}</p>
          <p className="mt-1 text-xs font-semibold uppercase text-gold">{item.target_module}</p>
        </div>
        <ImpactBadge impact={item.priority} />
      </div>
      <p className="mt-3 text-sm text-stone">{item.reason}</p>
      <p className="mt-3 rounded-lg bg-gold/10 p-3 text-sm font-semibold text-gold">{item.action}</p>
      {item.persisted ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onStatus(item.insight_id, "resolved")}
            className="rounded-full border border-surface-03 px-3 py-1.5 text-xs font-semibold text-cream hover:border-gold/50"
          >
            Resolver
          </button>
          <button
            type="button"
            onClick={() => onStatus(item.insight_id, "ignored")}
            className="rounded-full border border-surface-03 px-3 py-1.5 text-xs font-semibold text-stone hover:text-cream"
          >
            Ignorar
          </button>
          <button
            type="button"
            onClick={() => onStatus(item.insight_id, "postponed")}
            className="rounded-full border border-surface-03 px-3 py-1.5 text-xs font-semibold text-stone hover:text-cream"
          >
            Adiar
          </button>
        </div>
      ) : (
        <p className="mt-3 text-xs text-stone">Rode a analise para liberar acoes desta recomendacao.</p>
      )}
    </div>
  );
}

export default function BiDashboard() {
  const [period, setPeriod] = useState<ApiBIPeriod>("30d");
  const [data, setData] = useState<ApiBIDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (nextPeriod = period, silent = false) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const result = await biApi.dashboard({ period: nextPeriod });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar BI.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load(period);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  const runAnalysis = async () => {
    setRunning(true);
    setError(null);
    try {
      await biApi.runAnalysis({ period });
      await load(period, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao executar analise.");
    } finally {
      setRunning(false);
    }
  };

  const updateRecommendationStatus = async (
    insightId: string,
    status: "resolved" | "ignored" | "postponed",
  ) => {
    setRefreshing(true);
    setError(null);
    try {
      await biApi.updateInsightStatus(insightId, status);
      await load(period, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar recomendacao.");
    } finally {
      setRefreshing(false);
    }
  };

  const maxRevenue = useMemo(
    () => Math.max(...(data?.products ?? []).map((item) => item.total_revenue), 1),
    [data?.products],
  );
  const maxSales = useMemo(
    () => Math.max(...(data?.sales ?? []).map((item) => item.revenue), 1),
    [data?.sales],
  );

  if (loading && !data) {
    return (
      <div className="flex min-h-[420px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gold" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border border-surface-03 bg-surface-02 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          {PERIODS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setPeriod(item.key)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                period === item.key
                  ? "bg-gold text-surface-00"
                  : "border border-surface-03 bg-surface-01 text-stone hover:text-cream"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {data && (
            <span className="hidden text-xs text-stone sm:inline">
              {data.date_from} ate {data.date_to}
            </span>
          )}
          <button
            type="button"
            onClick={() => load(period, true)}
            className="inline-flex items-center gap-2 rounded-full border border-surface-03 bg-surface-01 px-4 py-2 text-sm font-semibold text-cream hover:border-gold/50"
          >
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
            Atualizar
          </button>
          <button
            type="button"
            onClick={runAnalysis}
            className="inline-flex items-center gap-2 rounded-full bg-gold px-4 py-2 text-sm font-bold text-surface-00 hover:bg-gold/90"
          >
            {running ? <Loader2 size={16} className="animate-spin" /> : <Brain size={16} />}
            Rodar analise
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            {data.kpis.map((kpi) => (
              <KpiCard key={kpi.key} kpi={kpi} />
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <Section title="Vendas por dia">
              <div className="space-y-3 rounded-xl border border-surface-03 bg-surface-02 p-4">
                {data.sales.length ? data.sales.map((item) => (
                  <div key={item.label} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-stone">{item.label}</span>
                      <span className="font-semibold text-cream">{money(item.revenue)}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface-01">
                      <div
                        className="h-full rounded-full bg-gold"
                        style={{ width: `${Math.max((item.revenue / maxSales) * 100, item.revenue ? 5 : 0)}%` }}
                      />
                    </div>
                  </div>
                )) : <EmptyState label="Sem vendas para o periodo selecionado." />}
              </div>
            </Section>

            <Section title="Funil comportamental">
              <div className="space-y-3 rounded-xl border border-surface-03 bg-surface-02 p-4">
                {data.funnel.length ? data.funnel.map((item) => (
                  <div key={item.key} className="flex items-center justify-between gap-3 rounded-lg bg-surface-01 px-3 py-2">
                    <div>
                      <p className="text-sm font-semibold text-cream">{item.label}</p>
                      <p className="text-xs text-stone">{item.conversion_pct.toFixed(1)}% conversao</p>
                    </div>
                    <span className="text-lg font-bold text-gold">{number(item.value)}</span>
                  </div>
                )) : <EmptyState label="Sem eventos comportamentais no periodo." />}
              </div>
            </Section>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Section title="Produtos e Pareto 80/20">
              <div className="space-y-3 rounded-xl border border-surface-03 bg-surface-02 p-4">
                {data.products.length ? data.products.map((product) => (
                  <div key={product.product_id ?? product.name} className="space-y-2">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-cream">
                          {product.is_top_20_percent && <Package className="mr-1 inline h-4 w-4 text-gold" />}
                          {product.name}
                        </p>
                        <p className="text-xs text-stone">
                          {number(product.quantity_sold)} itens | {product.share_pct.toFixed(1)}% da receita
                        </p>
                      </div>
                      <span className="text-sm font-bold text-gold">{money(product.total_revenue)}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-surface-01">
                      <div
                        className="h-full rounded-full bg-gold"
                        style={{ width: `${Math.max((product.total_revenue / maxRevenue) * 100, 5)}%` }}
                      />
                    </div>
                  </div>
                )) : <EmptyState label="Sem produtos vendidos no periodo." />}
              </div>
            </Section>

            <Section title="Segmentos automaticos">
              <div className="grid gap-3 sm:grid-cols-2">
                {data.customer_segments.map((segment) => (
                  <div key={segment.key} className="rounded-xl border border-surface-03 bg-surface-02 p-4">
                    <p className="text-sm font-bold text-cream">{segment.name}</p>
                    <p className="mt-1 text-xs text-stone">{segment.description}</p>
                    <p className="mt-3 text-2xl font-bold text-gold">{number(segment.total_customers)}</p>
                  </div>
                ))}
              </div>
            </Section>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Section title="Insights">
              <div className="space-y-3">
                {data.insights.length ? data.insights.map((item) => (
                  <InsightCard key={item.id} item={item} />
                )) : <EmptyState label="Sem insights para o periodo selecionado." />}
              </div>
            </Section>

            <Section title="Recomendacoes acionaveis">
              <div className="space-y-3">
                {data.recommendations.length ? data.recommendations.map((item) => (
                  <RecommendationCard key={item.id} item={item} onStatus={updateRecommendationStatus} />
                )) : <EmptyState label="Nenhuma recomendacao acionavel no momento." />}
              </div>
            </Section>
          </div>

          <Section title="Clientes de maior valor">
            <div className="overflow-hidden rounded-xl border border-surface-03 bg-surface-02">
              {data.top_customers.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-sm">
                    <thead className="bg-surface-01 text-xs uppercase text-stone">
                      <tr>
                        <th className="px-4 py-3 text-left">Cliente</th>
                        <th className="px-4 py-3 text-left">Pedidos</th>
                        <th className="px-4 py-3 text-left">Total gasto</th>
                        <th className="px-4 py-3 text-left">Ticket medio</th>
                        <th className="px-4 py-3 text-left">Ultimo pedido</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_customers.map((customer) => (
                        <tr key={customer.customer_id} className="border-t border-surface-03 text-cream">
                          <td className="px-4 py-3 font-semibold">{customer.name}</td>
                          <td className="px-4 py-3 text-stone">{number(customer.total_orders)}</td>
                          <td className="px-4 py-3 text-gold">{money(customer.total_spent)}</td>
                          <td className="px-4 py-3 text-stone">{money(customer.avg_ticket)}</td>
                          <td className="px-4 py-3 text-stone">
                            {customer.last_order_at ? new Date(customer.last_order_at).toLocaleDateString("pt-BR") : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState label="Sem clientes com historico de compra." />
              )}
            </div>
          </Section>
        </>
      ) : (
        <EmptyState label="Nao foi possivel carregar os dados de BI." />
      )}
    </div>
  );
}
