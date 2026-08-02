import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Building2,
  CalendarClock,
  CircleDollarSign,
  Globe2,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { platformTenantsApi, type ApiPlatformDashboard } from "@/lib/api";

export default function PlatformDashboard() {
  const [data, setData] = useState<ApiPlatformDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await platformTenantsApi.dashboard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar os indicadores.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading) {
    return <div className="flex min-h-72 items-center justify-center gap-2 text-stone"><Loader2 className="animate-spin text-gold" /> Carregando indicadores...</div>;
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">
        <p>{error || "Dados indisponiveis."}</p>
        <Button variant="outline" className="mt-4 gap-2" onClick={() => void load()}><RefreshCw size={15} /> Tentar novamente</Button>
      </div>
    );
  }

  const metrics = [
    { key: "tenant-total", label: "Total de empresas", value: data.metrics.total_tenants, icon: Building2 },
    { key: "tenant-active", label: "Empresas ativas", value: data.metrics.active_tenants, icon: Building2 },
    { key: "tenant-created", label: "Cadastradas no mes", value: data.metrics.created_month, icon: Building2 },
    { key: "users-total", label: "Total de usuarios", value: data.metrics.total_users, icon: Users },
    { key: "tenant-suspended", label: "Empresas suspensas", value: data.tenants.suspended, icon: ShieldAlert },
    { key: "tenant-disabled", label: "Empresas desativadas", value: data.tenants.disabled, icon: ShieldAlert },
    { key: "license-trial", label: "Empresas em teste", value: data.metrics.trial_licenses, icon: CalendarClock },
    { key: "license-active", label: "Licencas ativas", value: data.metrics.active_licenses, icon: CalendarClock },
    { key: "license-expired", label: "Licencas vencidas", value: data.metrics.expired_licenses, icon: AlertTriangle },
    { key: "license-blocked", label: "Licencas bloqueadas", value: data.licenses.blocked, icon: ShieldAlert },
    { key: "license-cancelled", label: "Licencas canceladas", value: data.licenses.cancelled, icon: ShieldAlert },
    { key: "license-expiring", label: "Vencendo em 7 dias", value: data.licenses.expiring_7d, icon: CalendarClock },
    { key: "domain-active", label: "Dominios ativos", value: data.metrics.active_domains, icon: Globe2 },
    { key: "domain-pending", label: "Dominios pendentes", value: data.domains.pending, icon: Globe2 },
    { key: "domain-error", label: "Dominios com erro", value: data.metrics.domain_errors, icon: Globe2 },
    { key: "users-limit", label: "Limites de usuarios atingidos", value: data.metrics.user_limits_reached, icon: Users },
    { key: "billing-pending-count", label: "Cobrancas pendentes", value: data.metrics.pending_invoices, icon: CircleDollarSign },
    { key: "billing-overdue", label: "Cobrancas atrasadas", value: data.metrics.overdue_invoices, icon: CircleDollarSign },
    {
      key: "billing-mrr",
      label: "Receita recorrente mensal",
      value: Number(data.metrics.mrr).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }),
      icon: CircleDollarSign,
    },
    {
      key: "billing-pending",
      label: "Valor pendente",
      value: Number(data.billing.pending_total).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }),
      icon: CircleDollarSign,
    },
  ];
  const activeAlerts = data.alerts.filter((alert) => alert.count > 0);

  return (
    <div className="space-y-6">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-5">
        {metrics.map(({ key, label, icon: Icon, value }) => {
          const formatted = typeof value === "number" ? value.toLocaleString("pt-BR") : value;
          return (
            <article key={key} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gold/10 text-gold"><Icon size={17} /></span>
                <span className="text-2xl font-black text-cream">{formatted}</span>
              </div>
              <p className="mt-3 text-xs font-semibold text-stone">{label}</p>
            </article>
          );
        })}
      </section>

      <section className="rounded-2xl border border-surface-03 bg-surface-02">
        <div className="flex items-center justify-between border-b border-surface-03 px-5 py-4">
          <div>
            <h2 className="font-black text-cream">Alertas operacionais</h2>
            <p className="mt-1 text-xs text-stone">Pendencias calculadas pelo backend.</p>
          </div>
          <span className="rounded-full bg-surface-01 px-3 py-1 text-xs font-bold text-gold">{activeAlerts.length}</span>
        </div>
        {!activeAlerts.length ? (
          <div className="p-10 text-center text-sm text-stone">Nenhum alerta ativo.</div>
        ) : (
          <div className="divide-y divide-surface-03">
            {activeAlerts.map((alert) => (
              <Link
                key={alert.key}
                to={alert.tenant_ids[0] ? `/painel/empresas/${alert.tenant_ids[0]}` : "/painel/empresas"}
                className="flex items-start gap-3 p-5 transition hover:bg-surface-03/40"
              >
                <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  alert.severity === "critical" ? "bg-red-500/10 text-red-300" :
                  alert.severity === "warning" ? "bg-yellow-500/10 text-yellow-200" :
                  "bg-blue-500/10 text-blue-300"
                }`}><AlertTriangle size={17} /></span>
                <span className="min-w-0">
                  <span className="block font-bold text-cream">{alert.title}</span>
                  <span className="mt-1 block text-sm text-stone">{alert.description}</span>
                </span>
                <span className="ml-auto rounded-full bg-surface-01 px-3 py-1 text-xs font-black text-gold">{alert.count}</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
