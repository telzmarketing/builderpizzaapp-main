import { useCallback, useEffect, useState } from "react";
import { ArrowRight, CircleDollarSign, Loader2, RefreshCw, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { LicenseStatusBadge } from "@/components/platform/PlatformComponents";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  platformTenantsApi,
  type ApiPlatformPage,
  type ApiPlatformTenant,
} from "@/lib/api";

const EMPTY: ApiPlatformPage<ApiPlatformTenant> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  pages: 0,
};

const BILLING_LABELS = {
  ok: "Em dia",
  pending: "Pendente",
  overdue: "Em atraso",
} as const;

function billingClass(status?: ApiPlatformTenant["billing_status"]) {
  if (status === "overdue") return "border-red-500/30 bg-red-500/10 text-red-200";
  if (status === "pending") return "border-yellow-500/30 bg-yellow-500/10 text-yellow-100";
  return "border-green-500/30 bg-green-500/10 text-green-200";
}

export default function PlatformBillingOverview() {
  const [data, setData] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState(() => new URLSearchParams(window.location.search).get("status") || "overdue");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await platformTenantsApi.list({
        page,
        page_size: 20,
        q: query.trim() || undefined,
        billing_status: status || undefined,
        sort_by: "name",
        sort_dir: "asc",
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar as cobrancas.");
    } finally {
      setLoading(false);
    }
  }, [page, query, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
        <div className="flex flex-col gap-3 lg:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone" />
            <Input
              value={query}
              onChange={(event) => { setQuery(event.target.value); setPage(1); }}
              placeholder="Buscar empresa"
              className="border-surface-03 bg-surface-01 pl-9 text-cream"
            />
          </div>
          <select
            value={status}
            onChange={(event) => { setStatus(event.target.value); setPage(1); }}
            className="h-10 rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream"
          >
            <option value="">Todas as situacoes</option>
            <option value="overdue">Em atraso</option>
            <option value="pending">Pendentes</option>
            <option value="ok">Em dia</option>
          </select>
        </div>
        <p className="mt-3 text-xs text-stone">A situacao vem das faturas da empresa. Valores e pagamentos permanecem no historico financeiro do detalhe.</p>
      </section>

      {error && (
        <div className="flex flex-col gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200 sm:flex-row sm:items-center sm:justify-between">
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => void load()} className="gap-2"><RefreshCw size={14} /> Tentar novamente</Button>
        </div>
      )}

      <section className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
        <div className="flex items-center justify-between border-b border-surface-03 px-5 py-4">
          <div>
            <h2 className="flex items-center gap-2 font-black text-cream"><CircleDollarSign size={18} className="text-gold" /> Empresas por situacao financeira</h2>
            <p className="mt-1 text-xs text-stone">{data.total} registro(s)</p>
          </div>
          {loading && <Loader2 size={18} className="animate-spin text-gold" />}
        </div>

        {!loading && !data.items.length ? (
          <div className="p-10 text-center">
            <p className="font-bold text-cream">Nenhuma empresa encontrada</p>
            <p className="mt-1 text-sm text-stone">Altere a situacao financeira ou o termo de busca.</p>
          </div>
        ) : (
          <div className="divide-y divide-surface-03">
            {data.items.map((tenant) => (
              <article key={tenant.id} className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate font-black text-cream">{tenant.name}</h3>
                    <span className={`rounded-full border px-2 py-1 text-xs font-bold ${billingClass(tenant.billing_status)}`}>
                      {tenant.billing_status ? BILLING_LABELS[tenant.billing_status] : "Nao configurada"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-stone">
                    {tenant.plan?.name || "Sem plano"} · Responsavel: {tenant.responsible || "nao informado"}
                  </p>
                  {tenant.license && <div className="mt-2"><LicenseStatusBadge status={tenant.license.status} /></div>}
                </div>
                <Button asChild variant="outline" className="gap-2">
                  <Link to={`/painel/empresas/${tenant.id}?tab=Cobrancas`}>Abrir cobrancas <ArrowRight size={14} /></Link>
                </Button>
              </article>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-3 border-t border-surface-03 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <span className="text-stone">Pagina {data.page} de {Math.max(1, data.pages)}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={loading || page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</Button>
            <Button variant="outline" size="sm" disabled={loading || page >= data.pages} onClick={() => setPage((current) => current + 1)}>Proxima</Button>
          </div>
        </div>
      </section>
    </div>
  );
}
