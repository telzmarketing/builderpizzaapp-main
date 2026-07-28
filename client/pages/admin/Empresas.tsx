import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Building2, Globe2, Loader2, Plus, RefreshCw } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  platformTenantsApi,
  type ApiPlatformTenant,
  type ApiPlatformTenantDomain,
} from "@/lib/api";

type TenantForm = { name: string; slug: string };
type DomainForm = { tenantId: string; hostname: string; kind: "subdomain" | "custom" };

const EMPTY_TENANT: TenantForm = { name: "", slug: "" };
const EMPTY_DOMAIN: DomainForm = { tenantId: "", hostname: "", kind: "subdomain" };

function normalizeHostname(value: string) {
  return value.trim().toLowerCase().replace(/^https?:\/\//, "").split("/")[0];
}

export default function Empresas() {
  const { toast } = useToast();
  const [tenants, setTenants] = useState<ApiPlatformTenant[]>([]);
  const [domains, setDomains] = useState<Record<string, ApiPlatformTenantDomain[]>>({});
  const [loading, setLoading] = useState(true);
  const [savingTenant, setSavingTenant] = useState(false);
  const [savingDomain, setSavingDomain] = useState(false);
  const [error, setError] = useState("");
  const [tenantForm, setTenantForm] = useState<TenantForm>(EMPTY_TENANT);
  const [domainForm, setDomainForm] = useState<DomainForm>(EMPTY_DOMAIN);

  const sortedTenants = useMemo(
    () => [...tenants].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
    [tenants],
  );

  async function load() {
    setLoading(true);
    setError("");
    try {
      const items = await platformTenantsApi.list();
      setTenants(items);
      setDomainForm((current) => ({
        ...current,
        tenantId: current.tenantId || items[0]?.id || "",
      }));
      const entries = await Promise.all(
        items.map(async (tenant) => [tenant.id, await platformTenantsApi.listDomains(tenant.id)] as const),
      );
      setDomains(Object.fromEntries(entries));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar as empresas.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function createTenant(event: FormEvent) {
    event.preventDefault();
    setSavingTenant(true);
    try {
      const created = await platformTenantsApi.create({
        name: tenantForm.name.trim(),
        slug: tenantForm.slug.trim().toLowerCase(),
      });
      setTenants((items) => [...items, created]);
      setDomains((current) => ({ ...current, [created.id]: created.domains ?? [] }));
      setDomainForm((current) => ({ ...current, tenantId: created.id }));
      setTenantForm(EMPTY_TENANT);
      toast({ title: "Empresa cadastrada", description: "Seu acesso administrativo foi vinculado a empresa." });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nao foi possivel cadastrar",
        description: err instanceof Error ? err.message : "Revise os dados e tente novamente.",
      });
    } finally {
      setSavingTenant(false);
    }
  }

  async function createDomain(event: FormEvent) {
    event.preventDefault();
    const hostname = normalizeHostname(domainForm.hostname);
    setSavingDomain(true);
    try {
      const created = await platformTenantsApi.createDomain(domainForm.tenantId, {
        hostname,
        kind: domainForm.kind,
      });
      setDomains((current) => ({
        ...current,
        [domainForm.tenantId]: [...(current[domainForm.tenantId] ?? []), created.domain],
      }));
      setDomainForm((current) => ({ ...current, hostname: "" }));
      toast({
        title: "Dominio cadastrado",
        description: `Crie ${created.verification.record_type} ${created.verification.record_name} = ${created.verification.record_value}.`,
      });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nao foi possivel cadastrar o dominio",
        description: err instanceof Error ? err.message : "Revise o hostname e tente novamente.",
      });
    } finally {
      setSavingDomain(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[20rem] items-center justify-center text-stone">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-gold" /> Carregando empresas...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-center justify-between rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          <span>{error}</span>
          <button type="button" onClick={() => void load()} className="flex items-center gap-2 font-bold">
            <RefreshCw className="h-4 w-4" /> Tentar novamente
          </button>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-2">
        <form onSubmit={createTenant} className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-5">
          <div className="flex items-center gap-3">
            <Building2 className="h-5 w-5 text-gold" />
            <div>
              <h2 className="font-bold text-cream">Nova empresa</h2>
              <p className="text-xs text-stone">Cria a empresa e vincula o administrador responsavel.</p>
            </div>
          </div>
          <input required value={tenantForm.name} onChange={(e) => setTenantForm({ ...tenantForm, name: e.target.value })} placeholder="Nome da empresa" className="w-full rounded-xl border border-surface-03 bg-surface-01 px-4 py-3 text-sm text-cream outline-none focus:border-gold/60" />
          <input required pattern="[a-z0-9-]+" value={tenantForm.slug} onChange={(e) => setTenantForm({ ...tenantForm, slug: e.target.value.replace(/[^a-zA-Z0-9-]/g, "") })} placeholder="Identificador (slug)" className="w-full rounded-xl border border-surface-03 bg-surface-01 px-4 py-3 text-sm text-cream outline-none focus:border-gold/60" />
          <button disabled={savingTenant} className="flex w-full items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-black text-surface-00 disabled:opacity-60">
            {savingTenant ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Cadastrar empresa
          </button>
        </form>

        <form onSubmit={createDomain} className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-5">
          <div className="flex items-center gap-3">
            <Globe2 className="h-5 w-5 text-gold" />
            <div>
              <h2 className="font-bold text-cream">Novo dominio</h2>
              <p className="text-xs text-stone">O dominio nasce pendente e nao publica a loja antes da verificacao.</p>
            </div>
          </div>
          <select required value={domainForm.tenantId} onChange={(e) => setDomainForm({ ...domainForm, tenantId: e.target.value })} className="w-full rounded-xl border border-surface-03 bg-surface-01 px-4 py-3 text-sm text-cream outline-none focus:border-gold/60">
            <option value="">Selecione a empresa</option>
            {sortedTenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
          </select>
          <input required value={domainForm.hostname} onChange={(e) => setDomainForm({ ...domainForm, hostname: e.target.value })} placeholder="loja.exemplo.com.br" className="w-full rounded-xl border border-surface-03 bg-surface-01 px-4 py-3 text-sm text-cream outline-none focus:border-gold/60" />
          <select value={domainForm.kind} onChange={(e) => setDomainForm({ ...domainForm, kind: e.target.value as DomainForm["kind"] })} className="w-full rounded-xl border border-surface-03 bg-surface-01 px-4 py-3 text-sm text-cream outline-none focus:border-gold/60">
            <option value="subdomain">Subdominio</option>
            <option value="custom">Dominio proprio</option>
          </select>
          <button disabled={savingDomain || !sortedTenants.length} className="flex w-full items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-black text-surface-00 disabled:opacity-60">
            {savingDomain ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Cadastrar dominio
          </button>
        </form>
      </div>

      <section className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
        <div className="border-b border-surface-03 px-5 py-4">
          <h2 className="font-bold text-cream">Empresas cadastradas</h2>
          <p className="text-xs text-stone">{sortedTenants.length} empresa(s) disponivel(is)</p>
        </div>
        {!sortedTenants.length ? (
          <div className="p-8 text-center text-sm text-stone">Nenhuma empresa cadastrada.</div>
        ) : (
          <div className="divide-y divide-surface-03">
            {sortedTenants.map((tenant) => (
              <article key={tenant.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-bold text-cream">{tenant.name}</h3>
                    <p className="text-xs text-stone">{tenant.slug}</p>
                  </div>
                  <span className="rounded-full border border-surface-03 px-3 py-1 text-xs font-bold text-gold">{tenant.status}</span>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {(domains[tenant.id] ?? []).map((domain) => (
                    <span key={domain.id} className="rounded-lg bg-surface-01 px-3 py-2 text-xs text-stone">
                      <strong className="text-cream">{domain.hostname}</strong> · {domain.kind} · {domain.status}
                    </span>
                  ))}
                  {!(domains[tenant.id] ?? []).length && <span className="text-xs text-stone/70">Sem dominios.</span>}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
