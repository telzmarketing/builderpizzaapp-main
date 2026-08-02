import { useCallback, useEffect, useState } from "react";
import { Archive, ArrowDownUp, Loader2, MoreHorizontal, RefreshCw, Search, ShieldOff, SlidersHorizontal, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import CreateCompanyWizard from "@/components/platform/CreateCompanyWizard";
import {
  ConfirmationDialog,
  DomainStatusBadge,
  LicenseStatusBadge,
  StatusBadge,
} from "@/components/platform/PlatformComponents";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import {
  platformModulesApi,
  platformPlansApi,
  platformTenantsApi,
  type ApiPlatformModule,
  type ApiPlatformPage,
  type ApiPlatformPlan,
  type ApiPlatformTenant,
} from "@/lib/api";

const EMPTY_PAGE: ApiPlatformPage<ApiPlatformTenant> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  pages: 0,
};

function tenantLicenseEnd(tenant: ApiPlatformTenant) {
  if (!tenant.license) return null;
  return tenant.license.status === "trial"
    ? tenant.license.trial_ends_at || tenant.license.expires_at || null
    : tenant.license.expires_at || null;
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString("pt-BR") : "Nunca";
}

export default function Empresas() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [result, setResult] = useState(EMPTY_PAGE);
  const [plans, setPlans] = useState<ApiPlatformPlan[]>([]);
  const [modules, setModules] = useState<ApiPlatformModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [tenantId, setTenantId] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [planId, setPlanId] = useState("");
  const [domain, setDomain] = useState("");
  const [billingStatus, setBillingStatus] = useState("");
  const [moduleKey, setModuleKey] = useState("");
  const [expiringDays, setExpiringDays] = useState("");
  const [page, setPage] = useState(1);
  const [actionTenant, setActionTenant] = useState<ApiPlatformTenant | null>(null);
  const [action, setAction] = useState<"suspend" | "reactivate" | "archive" | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await platformTenantsApi.list({
        page,
        page_size: 20,
        q: query.trim() || undefined,
        status: status || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        tenant_id: tenantId.trim() || undefined,
        email: ownerEmail.trim() || undefined,
        plan_id: planId || undefined,
        domain: domain.trim() || undefined,
        billing_status: billingStatus || undefined,
        module: moduleKey || undefined,
        expiring_days: expiringDays === "" ? undefined : Number(expiringDays),
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar as empresas.");
    } finally {
      setLoading(false);
    }
  }, [billingStatus, domain, expiringDays, moduleKey, ownerEmail, page, planId, query, sortBy, sortDir, status, tenantId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  useEffect(() => {
    Promise.allSettled([platformPlansApi.list(), platformModulesApi.list()]).then(([planResult, moduleResult]) => {
      if (planResult.status === "fulfilled") setPlans(planResult.value);
      if (moduleResult.status === "fulfilled") setModules(moduleResult.value);
    });
  }, []);

  async function executeAction() {
    if (!actionTenant || !action) return;
    try {
      await platformTenantsApi.action(actionTenant.id, action, reason.trim());
      toast({ title: "Empresa atualizada", description: "A acao foi registrada na auditoria." });
      setActionTenant(null);
      setAction(null);
      setReason("");
      await load();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nao foi possivel concluir",
        description: err instanceof Error ? err.message : "Tente novamente.",
      });
    }
  }

  const actionTitle = action === "suspend" ? "Suspender empresa"
    : action === "reactivate" ? "Reativar empresa"
    : "Arquivar empresa";

  const hasAdvancedFilters = Boolean(
    tenantId || ownerEmail || planId || domain || billingStatus || moduleKey || expiringDays,
  );

  function clearAdvancedFilters() {
    setTenantId("");
    setOwnerEmail("");
    setPlanId("");
    setDomain("");
    setBillingStatus("");
    setModuleKey("");
    setExpiringDays("");
    setPage(1);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-1 flex-col gap-3 sm:flex-row">
          <div className="relative min-w-0 flex-1 xl:max-w-xl">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone" />
            <Input
              value={query}
              onChange={(event) => { setQuery(event.target.value); setPage(1); }}
              placeholder="Buscar por nome, razao social, slug ou documento"
              className="border-surface-03 bg-surface-02 pl-9 text-cream"
            />
          </div>
          <select
            value={status}
            onChange={(event) => { setStatus(event.target.value); setPage(1); }}
            className="h-10 rounded-md border border-surface-03 bg-surface-02 px-3 text-sm text-cream"
          >
            <option value="">Todos os status</option>
            <option value="active">Tenant ativo</option>
            <option value="suspended">Tenant suspenso</option>
            <option value="disabled">Tenant desativado</option>
            <option value="trial">Licenca em teste</option>
            <option value="grace_period">Licenca em carencia</option>
            <option value="expired">Licenca vencida</option>
            <option value="blocked">Licenca bloqueada</option>
            <option value="cancelled">Licenca cancelada</option>
          </select>
          <select
            value={sortBy}
            onChange={(event) => { setSortBy(event.target.value); setPage(1); }}
            className="h-10 rounded-md border border-surface-03 bg-surface-02 px-3 text-sm text-cream"
          >
            <option value="created_at">Data de criacao</option>
            <option value="name">Nome</option>
            <option value="updated_at">Ultima atualizacao</option>
            <option value="license_ends_at">Vencimento da licenca</option>
            <option value="status">Status</option>
          </select>
          <Button
            variant="outline"
            size="icon"
            title={sortDir === "asc" ? "Ordem crescente" : "Ordem decrescente"}
            onClick={() => setSortDir((current) => current === "asc" ? "desc" : "asc")}
          >
            <ArrowDownUp size={16} />
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowAdvancedFilters((current) => !current)}
            className="gap-2"
          >
            <SlidersHorizontal size={15} /> Filtros
            {hasAdvancedFilters && <span className="h-2 w-2 rounded-full bg-gold" />}
          </Button>
        </div>
        <CreateCompanyWizard
          plans={plans}
          modules={modules}
          onCreated={(created) => {
            toast({ title: "Empresa criada", description: "O provisionamento foi concluido em uma unica transacao." });
            navigate(`/painel/empresas/${created.tenant.id}`);
          }}
        />
      </div>

      {showAdvancedFilters && (
        <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Input value={tenantId} onChange={(event) => { setTenantId(event.target.value); setPage(1); }} placeholder="Tenant ID exato" className="border-surface-03 bg-surface-01 text-cream" />
            <Input value={ownerEmail} onChange={(event) => { setOwnerEmail(event.target.value); setPage(1); }} placeholder="E-mail do owner" className="border-surface-03 bg-surface-01 text-cream" />
            <Input value={domain} onChange={(event) => { setDomain(event.target.value); setPage(1); }} placeholder="Dominio" className="border-surface-03 bg-surface-01 text-cream" />
            <select value={planId} onChange={(event) => { setPlanId(event.target.value); setPage(1); }} className="h-10 rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream">
              <option value="">Todos os planos</option>
              {plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}
            </select>
            <select value={moduleKey} onChange={(event) => { setModuleKey(event.target.value); setPage(1); }} className="h-10 rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream">
              <option value="">Todos os modulos</option>
              {modules.filter((module) => module.active).map((module) => <option key={module.id} value={module.key}>{module.name}</option>)}
            </select>
            <select value={billingStatus} onChange={(event) => { setBillingStatus(event.target.value); setPage(1); }} className="h-10 rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream">
              <option value="">Qualquer financeiro</option>
              <option value="ok">Em dia</option>
              <option value="pending">Pendente</option>
              <option value="overdue">Em atraso</option>
            </select>
            <label className="flex h-10 items-center gap-2 rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-stone">
              <span className="whitespace-nowrap">Expira em ate</span>
              <Input type="number" min={0} max={3650} value={expiringDays} onChange={(event) => { setExpiringDays(event.target.value); setPage(1); }} placeholder="dias" className="h-8 border-0 bg-transparent px-1 text-cream" />
            </label>
            <Button variant="ghost" disabled={!hasAdvancedFilters} onClick={clearAdvancedFilters} className="gap-2 text-stone">
              <X size={15} /> Limpar filtros
            </Button>
          </div>
        </section>
      )}

      {error && (
        <div className="flex flex-col gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200 sm:flex-row sm:items-center sm:justify-between">
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => void load()} className="gap-2">
            <RefreshCw size={14} /> Tentar novamente
          </Button>
        </div>
      )}

      <section className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
        <div className="flex items-center justify-between border-b border-surface-03 px-5 py-4">
          <div>
            <h2 className="font-black text-cream">Empresas cadastradas</h2>
            <p className="mt-1 text-xs text-stone">{result.total} registro(s)</p>
          </div>
          {loading && <Loader2 size={18} className="animate-spin text-gold" />}
        </div>

        {!loading && !result.items.length ? (
          <div className="p-10 text-center">
            <p className="font-bold text-cream">Nenhuma empresa encontrada</p>
            <p className="mt-1 text-sm text-stone">Ajuste os filtros ou cadastre a primeira empresa.</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-surface-03 hover:bg-transparent">
                <TableHead>Empresa</TableHead>
                <TableHead>Plano</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Responsavel</TableHead>
                <TableHead>Licenca</TableHead>
                <TableHead>Usuarios</TableHead>
                <TableHead>Dominio principal</TableHead>
                <TableHead>Financeiro</TableHead>
                <TableHead>Criada em</TableHead>
                <TableHead className="w-14" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.items.map((tenant) => (
                <TableRow
                  key={tenant.id}
                  className="cursor-pointer border-surface-03"
                  onClick={() => navigate(`/painel/empresas/${tenant.id}`)}
                >
                  <TableCell>
                    <p className="font-bold text-cream">{tenant.name}</p>
                    <p className="mt-1 max-w-64 truncate text-xs text-stone">{tenant.trade_name || tenant.legal_name || tenant.slug}</p>
                    <p className="mt-1 max-w-64 truncate text-[11px] text-stone">{tenant.document || tenant.id}</p>
                  </TableCell>
                  <TableCell className="text-stone">{tenant.plan?.name || "Sem plano"}</TableCell>
                  <TableCell><StatusBadge status={tenant.status} /></TableCell>
                  <TableCell>
                    <p className="max-w-44 truncate text-sm text-cream">{tenant.responsible || "Nao informado"}</p>
                    <p className="mt-1 text-[11px] text-stone">Ultimo acesso: {formatDateTime(tenant.last_access)}</p>
                  </TableCell>
                  <TableCell>
                    {tenant.license ? (
                      <div className="space-y-1">
                        <LicenseStatusBadge status={tenant.license.status} />
                        <p className="text-[11px] text-stone">
                          {tenantLicenseEnd(tenant) ? `Ate ${new Date(tenantLicenseEnd(tenant)!).toLocaleDateString("pt-BR")}` : "Sem termino definido"}
                          {tenant.days_remaining != null ? ` · ${tenant.days_remaining} dia(s)` : ""}
                        </p>
                      </div>
                    ) : <span className="text-stone">Nao configurada</span>}
                  </TableCell>
                  <TableCell className="text-stone">{tenant.user_count ?? tenant.users_count ?? 0}{tenant.plan?.max_users ? ` / ${tenant.plan.max_users}` : ""}</TableCell>
                  <TableCell>
                    <p className="max-w-56 truncate text-stone">{tenant.primary_domain?.hostname || "Sem dominio ativo"}</p>
                    {(tenant.domain_status || tenant.primary_domain?.status) && (
                      <div className="mt-1"><DomainStatusBadge status={(tenant.domain_status || tenant.primary_domain?.status)!} /></div>
                    )}
                  </TableCell>
                  <TableCell className={tenant.billing_status === "overdue" ? "font-bold text-red-300" : "text-stone"}>
                    {tenant.billing_status === "overdue" ? "Em atraso" : tenant.billing_status === "pending" ? "Pendente" : "Em dia"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-stone">{new Date(tenant.created_at).toLocaleDateString("pt-BR")}</TableCell>
                  <TableCell onClick={(event) => event.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label={`Acoes de ${tenant.name}`}><MoreHorizontal size={17} /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => navigate(`/painel/empresas/${tenant.id}`)}>Abrir detalhes</DropdownMenuItem>
                        <DropdownMenuSeparator />
                        {tenant.status === "suspended" ? (
                          <DropdownMenuItem onClick={() => { setActionTenant(tenant); setAction("reactivate"); }}>Reativar</DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem onClick={() => { setActionTenant(tenant); setAction("suspend"); }}>
                            <ShieldOff size={14} className="mr-2" /> Suspender
                          </DropdownMenuItem>
                        )}
                        {!tenant.is_legacy && (
                          <DropdownMenuItem className="text-red-600" onClick={() => { setActionTenant(tenant); setAction("archive"); }}>
                            <Archive size={14} className="mr-2" /> Arquivar
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <div className="flex flex-col gap-3 border-t border-surface-03 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <span className="text-stone">Pagina {result.page} de {Math.max(1, result.pages)}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={loading || page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</Button>
            <Button variant="outline" size="sm" disabled={loading || page >= result.pages} onClick={() => setPage((current) => current + 1)}>Proxima</Button>
          </div>
        </div>
      </section>

      {actionTenant && action && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setActionTenant(null);
              setAction(null);
              setReason("");
            }
          }}
          title={actionTitle}
          description={`Esta acao altera o acesso de ${actionTenant.name} e sera auditada.`}
          confirmLabel="Confirmar"
          destructive={action !== "reactivate"}
          reason={reason}
          reasonRequired
          onReasonChange={setReason}
          onConfirm={() => void executeAction()}
        />
      )}
    </div>
  );
}
