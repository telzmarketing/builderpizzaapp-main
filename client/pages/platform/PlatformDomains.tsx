import { useCallback, useEffect, useState } from "react";
import { Copy, Loader2, RefreshCw, Search, Trash2 } from "lucide-react";
import {
  ConfirmationDialog,
  DomainStatusBadge,
} from "@/components/platform/PlatformComponents";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import {
  platformDomainsApi,
  type ApiPlatformPage,
  type ApiPlatformTenantDomain,
} from "@/lib/api";

const EMPTY: ApiPlatformPage<ApiPlatformTenantDomain> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  pages: 0,
};

export default function PlatformDomains() {
  const { toast } = useToast();
  const [data, setData] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionTarget, setActionTarget] =
    useState<ApiPlatformTenantDomain | null>(null);
  const [destructiveAction, setDestructiveAction] = useState<
    "suspend" | "remove" | null
  >(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(
        await platformDomainsApi.list({
          page,
          page_size: 20,
          q: query.trim() || undefined,
          status: status || undefined,
        }),
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Nao foi possivel carregar os dominios.",
      );
    } finally {
      setLoading(false);
    }
  }, [page, query, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query ? 300 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  async function act(
    domain: ApiPlatformTenantDomain,
    action: "verify" | "activate" | "primary",
  ) {
    setBusyId(domain.id);
    try {
      await platformDomainsApi.action(domain.id, action);
      toast({
        title:
          action === "verify" ? "Teste DNS concluido" : "Dominio atualizado",
      });
      await load();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Acao nao concluida",
        description: err instanceof Error ? err.message : "Tente novamente.",
      });
    } finally {
      setBusyId(null);
    }
  }

  async function copyDns(value: string) {
    try {
      if (!navigator.clipboard)
        throw new Error("Area de transferencia indisponivel.");
      await navigator.clipboard.writeText(value);
      toast({ title: "Registro DNS copiado" });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Nao foi possivel copiar",
        description: err instanceof Error ? err.message : "Copie manualmente.",
      });
    }
  }

  function requestDestructive(
    domain: ApiPlatformTenantDomain,
    action: "suspend" | "remove",
  ) {
    setActionTarget(domain);
    setDestructiveAction(action);
    setReason("");
  }

  async function executeDestructive() {
    if (
      !actionTarget ||
      !destructiveAction ||
      reason.trim().length < 3 ||
      busyId
    )
      return;
    setBusyId(actionTarget.id);
    try {
      if (destructiveAction === "remove") {
        await platformDomainsApi.remove(actionTarget.id, reason.trim());
      } else {
        await platformDomainsApi.action(
          actionTarget.id,
          "suspend",
          reason.trim(),
        );
      }
      toast({
        title:
          destructiveAction === "remove"
            ? "Dominio removido"
            : "Dominio suspenso",
        description: "O motivo foi registrado na auditoria.",
      });
      setActionTarget(null);
      setDestructiveAction(null);
      setReason("");
      await load();
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Acao nao concluida",
        description: err instanceof Error ? err.message : "Tente novamente.",
      });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone" />
          <Input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar hostname ou tenant"
            className="border-surface-03 bg-surface-02 pl-9 text-cream"
          />
        </div>
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          className="h-10 rounded-md border border-surface-03 bg-surface-02 px-3 text-sm text-cream"
        >
          <option value="">Todos os status</option>
          <option value="awaiting_dns">Aguardando DNS</option>
          <option value="verifying">Verificando</option>
          <option value="verified">Verificados</option>
          <option value="active">Ativos</option>
          <option value="dns_error">Erro DNS</option>
          <option value="ssl_error">Erro SSL</option>
          <option value="suspended">Suspensos</option>
        </select>
      </div>
      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
          <Button
            variant="ghost"
            size="sm"
            className="ml-3 gap-1"
            onClick={() => void load()}
          >
            <RefreshCw size={13} /> Repetir
          </Button>
        </div>
      )}
      <section className="overflow-hidden rounded-2xl border border-surface-03 bg-surface-02">
        <div className="flex items-center justify-between border-b border-surface-03 p-4">
          <div>
            <h2 className="font-black text-cream">Dominios da plataforma</h2>
            <p className="mt-1 text-xs text-stone">{data.total} registro(s)</p>
          </div>
          {loading && <Loader2 size={17} className="animate-spin text-gold" />}
        </div>
        {!loading && !data.items.length ? (
          <div className="p-10 text-center text-sm text-stone">
            Nenhum dominio encontrado.
          </div>
        ) : (
          <div className="divide-y divide-surface-03">
            {data.items.map((domain) => (
              <article
                key={domain.id}
                className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-bold text-cream">
                      {domain.hostname}
                    </p>
                    <DomainStatusBadge status={domain.status} />
                    {domain.is_primary && (
                      <span className="rounded-full border border-gold/30 px-2 py-1 text-xs text-gold">
                        Principal
                      </span>
                    )}
                  </div>
                  <p className="mt-2 truncate text-xs text-stone">
                    Tenant {domain.tenant_id} · SSL{" "}
                    {domain.ssl_status || "pendente"}
                  </p>
                  {(domain.expected_txt_record || domain.expected_cname) && (
                    <button
                      type="button"
                      onClick={() => void copyDns((domain.expected_txt_record || domain.expected_cname)!)}
                      className="mt-2 inline-flex max-w-full items-center gap-2 text-xs text-stone hover:text-cream"
                    >
                      <span className="truncate">{domain.expected_txt_record || domain.expected_cname}</span>
                      <Copy size={12} className="shrink-0" />
                    </button>
                  )}
                  {domain.error_message && (
                    <p className="mt-2 text-xs text-red-300">
                      {domain.error_message}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {["pending", "awaiting_dns", "verifying", "dns_error"].includes(domain.status) && (
                    <Button variant="outline" size="sm" disabled={busyId === domain.id} onClick={() => void act(domain, "verify")}>
                      Testar DNS
                    </Button>
                  )}
                  {domain.status === "verified" && (
                    <Button
                      size="sm"
                      disabled={busyId === domain.id}
                      className="bg-green-600 text-white"
                      onClick={() => void act(domain, "activate")}
                    >
                      Ativar
                    </Button>
                  )}
                  {domain.status === "active" && !domain.is_primary && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busyId === domain.id}
                      onClick={() => void act(domain, "primary")}
                    >
                      Tornar principal
                    </Button>
                  )}
                  {domain.status === "active" && (
                    <Button asChild variant="outline" size="sm">
                      <a href={`https://${domain.hostname}`} target="_blank" rel="noreferrer">Testar acesso</a>
                    </Button>
                  )}
                  {domain.status === "active" && (
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={busyId === domain.id}
                      onClick={() => requestDestructive(domain, "suspend")}
                    >
                      Suspender
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busyId === domain.id}
                    onClick={() => requestDestructive(domain, "remove")}
                    className="gap-1 text-red-300"
                  >
                    <Trash2 size={13} /> Remover
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between border-t border-surface-03 p-4 text-sm">
          <span className="text-stone">
            Pagina {data.page} de {Math.max(1, data.pages)}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={loading || page <= 1}
              onClick={() => setPage((current) => current - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={loading || page >= data.pages}
              onClick={() => setPage((current) => current + 1)}
            >
              Proxima
            </Button>
          </div>
        </div>
      </section>
      {actionTarget && destructiveAction && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => {
            if (!open && !busyId) {
              setActionTarget(null);
              setDestructiveAction(null);
              setReason("");
            }
          }}
          title={destructiveAction === "remove" ? "Remover dominio" : "Suspender dominio"}
          description={`${actionTarget.hostname}: a acao sera auditada com o motivo informado.`}
          confirmLabel={busyId ? "Processando..." : destructiveAction === "remove" ? "Remover" : "Suspender"}
          destructive
          reason={reason}
          reasonRequired
          confirmDisabled={!!busyId || reason.trim().length < 3}
          preventCloseOnConfirm
          onReasonChange={setReason}
          onConfirm={() => void executeDestructive()}
        />
      )}
    </div>
  );
}
