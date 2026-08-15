import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BriefcaseBusiness, Clock3, KeyRound, Loader2, RefreshCw, Search, ShieldCheck, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  platformUsersApi,
  type ApiPlatformPage,
  type ApiPlatformUser,
  type ApiPlatformUserRole,
  type ApiPlatformUserStatus,
} from "@/lib/api";

export const PLATFORM_USERS_PAGE_SIZE = 20;

const EMPTY_PAGE: ApiPlatformPage<ApiPlatformUser> = {
  items: [], total: 0, page: 1, page_size: PLATFORM_USERS_PAGE_SIZE, pages: 0,
};

const SYSTEM_ROLES = [
  ["platform_owner", "Proprietario da Plataforma"],
  ["platform_admin", "Administrador da Plataforma"],
  ["platform_support", "Suporte da Plataforma"],
] as const;

export function platformUserRoleNames(roles: ApiPlatformUserRole[]): string {
  return roles.map((role) => role.name.trim()).filter(Boolean).join(", ") || "Sem papel";
}

export function platformUserEffectiveStatus(
  user: Pick<ApiPlatformUser, "active" | "status">,
): ApiPlatformUserStatus {
  return user.active && user.status === "active" ? "active" : "inactive";
}

function formatDate(value?: string | null): string {
  if (!value) return "Nunca";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Nao informado"
    : date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function statusClass(status: ApiPlatformUserStatus) {
  return status === "active"
    ? "border-green-500/30 bg-green-500/10 text-green-200"
    : "border-red-500/30 bg-red-500/10 text-red-200";
}

function RoleBadges({ roles }: { roles: ApiPlatformUserRole[] }) {
  if (!roles.length) return <span className="text-xs text-stone">Sem papel</span>;
  return <div className="flex flex-wrap gap-1.5">{roles.map((role) => (
    <span key={role.id} title={role.description || role.name} className="rounded-full border border-gold/25 bg-gold/10 px-2 py-1 text-[11px] font-bold text-gold">
      {role.name}
    </span>
  ))}</div>;
}

export default function PlatformUsers() {
  const [data, setData] = useState(EMPTY_PAGE);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"" | ApiPlatformUserStatus>("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const result = await platformUsersApi.list({
        page,
        page_size: PLATFORM_USERS_PAGE_SIZE,
        q: query.trim() || undefined,
        status: status || undefined,
        role: role || undefined,
      });
      if (requestId.current === currentRequest) setData(result);
    } catch (loadError) {
      if (requestId.current === currentRequest) {
        setError(loadError instanceof Error ? loadError.message : "Nao foi possivel carregar os usuarios da plataforma.");
      }
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [page, query, role, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query.trim() ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  const roleOptions = useMemo(() => {
    const options = new Map<string, string>(SYSTEM_ROLES);
    data.items.forEach((user) => user.platform_roles.forEach((item) => options.set(item.key, item.name)));
    return [...options].map(([key, name]) => ({ key, name }))
      .sort((left, right) => left.name.localeCompare(right.name, "pt-BR"));
  }, [data.items]);

  const pages = Math.max(1, data.pages);
  const first = data.total ? (data.page - 1) * data.page_size + 1 : 0;
  const last = data.total ? first + data.items.length - 1 : 0;

  return <div className="space-y-5">
    <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
      <div className="flex flex-col gap-3 xl:flex-row">
        <div className="relative min-w-0 flex-1">
          <Search size={16} aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 text-stone" />
          <Input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Buscar por nome ou e-mail" aria-label="Buscar usuarios da plataforma" className="border-surface-03 bg-surface-01 pl-9 text-cream" />
        </div>
        <select value={status} onChange={(event) => { setStatus(event.target.value as "" | ApiPlatformUserStatus); setPage(1); }} aria-label="Filtrar usuarios por status" className="h-10 rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream xl:w-48">
          <option value="">Todos os status</option><option value="active">Ativos</option><option value="inactive">Inativos</option>
        </select>
        <select value={role} onChange={(event) => { setRole(event.target.value); setPage(1); }} aria-label="Filtrar usuarios por papel" className="h-10 rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream xl:w-64">
          <option value="">Todos os papeis</option>
          {roleOptions.map((option) => <option key={option.key} value={option.key}>{option.name}</option>)}
        </select>
        <Button type="button" variant="outline" onClick={() => void load()} disabled={loading} className="gap-2 border-surface-03 bg-surface-01 text-cream">
          {loading ? <Loader2 className="animate-spin" /> : <RefreshCw />} Atualizar
        </Button>
      </div>
      <p className="mt-3 text-xs text-stone">Visualizacao somente leitura. Papeis e status representam o acesso global a Central Master.</p>
    </section>

    {error && <div role="alert" className="flex flex-col gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200 sm:flex-row sm:items-center sm:justify-between">
      <span>{error}</span><Button type="button" variant="outline" size="sm" onClick={() => void load()} className="gap-2"><RefreshCw /> Tentar novamente</Button>
    </div>}

    <section className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
      <div className="flex items-center justify-between gap-3 border-b border-surface-03 px-5 py-4">
        <div><h2 className="flex items-center gap-2 font-black text-cream"><Users size={18} className="text-gold" /> Operadores da plataforma</h2><p className="mt-1 text-xs text-stone">{data.total} usuario(s) encontrado(s)</p></div>
        {loading && <Loader2 size={18} aria-label="Carregando usuarios" className="animate-spin text-gold" />}
      </div>

      {loading && !data.items.length && !error ? <div className="flex min-h-56 items-center justify-center"><Loader2 size={24} className="animate-spin text-gold" /></div>
        : !loading && !error && !data.items.length ? <div className="p-10 text-center"><p className="font-bold text-cream">Nenhum usuario encontrado</p><p className="mt-1 text-sm text-stone">Altere a busca ou os filtros para consultar outros operadores.</p></div>
          : <>
            <div className="divide-y divide-surface-03 md:hidden">{data.items.map((user) => {
              const effectiveStatus = platformUserEffectiveStatus(user);
              return <article key={user.id} className="space-y-4 p-5">
                <div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="truncate font-black text-cream">{user.name}</h3><p className="truncate text-sm text-stone">{user.email}</p></div><span className={`rounded-full border px-2 py-1 text-xs font-bold ${statusClass(effectiveStatus)}`}>{effectiveStatus === "active" ? "Ativo" : "Inativo"}</span></div>
                <RoleBadges roles={user.platform_roles} />
                <dl className="grid grid-cols-2 gap-3 text-xs"><div><dt className="flex items-center gap-1 text-stone"><BriefcaseBusiness size={12} /> Cargo</dt><dd className="mt-1 text-cream">{user.job_title || "Nao informado"}</dd></div><div><dt className="flex items-center gap-1 text-stone"><Users size={12} /> Empresas</dt><dd className="mt-1 text-cream">{user.membership_count}</dd></div><div className="col-span-2"><dt className="flex items-center gap-1 text-stone"><Clock3 size={12} /> Ultimo acesso</dt><dd className="mt-1 text-cream">{formatDate(user.last_login_at)}</dd></div></dl>
                {user.force_password_change && <p className="flex items-center gap-2 text-xs font-bold text-yellow-100"><KeyRound size={13} /> Troca de senha pendente</p>}
              </article>;
            })}</div>

            <div className="hidden overflow-x-auto md:block"><table className="w-full min-w-[880px] text-sm">
              <thead className="bg-surface-03/40 text-left text-xs uppercase tracking-wide text-stone"><tr><th className="px-5 py-3">Usuario</th><th className="px-5 py-3">Papel global</th><th className="px-5 py-3">Cargo</th><th className="px-5 py-3">Empresas</th><th className="px-5 py-3">Ultimo acesso</th><th className="px-5 py-3">Status</th></tr></thead>
              <tbody className="divide-y divide-surface-03">{data.items.map((user) => {
                const effectiveStatus = platformUserEffectiveStatus(user);
                return <tr key={user.id} className="align-top hover:bg-surface-03/20"><td className="px-5 py-4"><p className="font-bold text-cream">{user.name}</p><p className="mt-1 text-xs text-stone">{user.email}</p>{user.phone && <p className="mt-1 text-xs text-stone">{user.phone}</p>}{user.force_password_change && <p className="mt-2 flex items-center gap-1 text-[11px] font-bold text-yellow-100"><KeyRound size={12} /> Troca de senha pendente</p>}</td><td className="px-5 py-4"><RoleBadges roles={user.platform_roles} /></td><td className="px-5 py-4 text-stone">{user.job_title || "Nao informado"}</td><td className="px-5 py-4 text-cream">{user.membership_count}</td><td className="whitespace-nowrap px-5 py-4 text-stone">{formatDate(user.last_login_at)}</td><td className="px-5 py-4"><span className={`inline-flex rounded-full border px-2 py-1 text-xs font-bold ${statusClass(effectiveStatus)}`}>{effectiveStatus === "active" ? "Ativo" : "Inativo"}</span></td></tr>;
              })}</tbody>
            </table></div>
          </>}

      <div className="flex flex-col gap-3 border-t border-surface-03 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="text-stone"><p>Pagina {data.page} de {pages}</p><p className="mt-1 text-xs">{data.total ? `Exibindo ${first}-${last} de ${data.total}` : "Nenhum registro para exibir"}</p></div>
        <div className="flex gap-2"><Button type="button" variant="outline" size="sm" disabled={loading || page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Anterior</Button><Button type="button" variant="outline" size="sm" disabled={loading || page >= data.pages} onClick={() => setPage((current) => current + 1)}>Proxima</Button></div>
      </div>
    </section>

    <p className="flex items-center gap-2 text-xs text-stone"><ShieldCheck size={14} className="text-gold" /> Esta tela nao cria, altera, bloqueia ou remove usuarios.</p>
  </div>;
}
