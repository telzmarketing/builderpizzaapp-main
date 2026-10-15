import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DomainStatusBadge } from "@/components/platform/PlatformComponents";
import {
  DomainCertificateDialog,
  DomainCertificateStatus,
} from "@/components/platform/DomainCertificateDialog";
import {
  companyDomainsApi,
  type ApiPlatformDomainCreation,
  type ApiPlatformTenantDomain,
} from "@/lib/api";

export default function TenantDomainsPanel() {
  const [canManage] = useState(() => {
    try {
      const permissions = JSON.parse(
        localStorage.getItem("admin_permissions") || "null",
      );
      return (
        permissions?.is_master === true ||
        permissions?.modules?.configuracoes?.edit === true
      );
    } catch {
      return false;
    }
  });
  const [items, setItems] = useState<ApiPlatformTenantDomain[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [hostname, setHostname] = useState("");
  const [kind, setKind] = useState<"subdomain" | "custom">("custom");
  const [challenge, setChallenge] = useState<
    ApiPlatformDomainCreation["verification"] | null
  >(null);
  const [selected, setSelected] = useState<ApiPlatformTenantDomain | null>(
    null,
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setItems(await companyDomainsApi.list());
      setLoaded(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Nao foi possivel carregar os dominios.",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManage || busy || !hostname.trim()) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await companyDomainsApi.create({
        hostname: hostname.trim(),
        kind,
      });
      setItems((current) => [result.domain, ...current]);
      setChallenge(result.verification);
      setHostname("");
      setMessage(
        "Dominio cadastrado. Guarde a prova TXT abaixo e abra Configurar HTTPS para consultar o apontamento DNS.",
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Nao foi possivel cadastrar o dominio.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function act(
    domain: ApiPlatformTenantDomain,
    action: "verify" | "activate",
  ) {
    if (!canManage || busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await companyDomainsApi[action](domain.id);
      setItems((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      if (action === "verify" && !["verified", "active"].includes(updated.status)) {
        setError("Nao foi possivel verificar o DNS. Confira o registro TXT e tente novamente.");
      } else {
        setMessage(
          action === "verify"
            ? "Verificacao DNS concluida. Configure HTTPS antes de ativar o dominio."
            : "Dominio ativado.",
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Nao foi possivel concluir a acao.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-bold text-cream">
            Dominio e HTTPS da sua empresa
          </h3>
          <p className="mt-1 text-sm text-stone">
            Cadastre o endereco, configure o DNS, solicite o certificado e
            acompanhe sua validade.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={loading || busy}
          onClick={() => void load()}
          className="gap-2"
        >
          <RefreshCw size={14} /> Atualizar
        </Button>
      </div>
      {!canManage && (
        <p className="text-sm text-stone">
          Acesso de leitura. Para alterar dominios ou solicitar HTTPS, solicite
          permissao de edicao de configuracoes.
        </p>
      )}
      {error && (
        <p
          role="alert"
          className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"
        >
          {error}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-200"
        >
          {message}
        </p>
      )}
      {loading ? (
        <div role="status" className="flex items-center gap-2 py-6 text-stone">
          <Loader2 size={18} className="animate-spin" /> Carregando dominios...
        </div>
      ) : (
        loaded && (
          <>
            <form
              onSubmit={(event) => void create(event)}
              className="grid gap-3 rounded-xl border border-surface-03 bg-surface-02 p-4 sm:grid-cols-[1fr_auto_auto]"
            >
              <label className="space-y-2 text-sm text-cream">
                <span>Endereco do dominio</span>
                <Input
                  required
                  value={hostname}
                  onChange={(event) => setHostname(event.target.value)}
                  disabled={busy || !canManage}
                  maxLength={253}
                  placeholder="pedidos.suaempresa.com.br"
                  className="border-surface-03 bg-surface-01"
                />
              </label>
              <label className="space-y-2 text-sm text-cream">
                <span>Tipo</span>
                <select
                  value={kind}
                  onChange={(event) =>
                    setKind(event.target.value as typeof kind)
                  }
                  disabled={busy || !canManage}
                  className="block h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3"
                >
                  <option value="custom">Dominio proprio</option>
                  <option value="subdomain">Subdominio da plataforma</option>
                </select>
              </label>
              <Button
                type="submit"
                disabled={busy || !canManage || !hostname.trim()}
                className="self-end gap-2 bg-gold text-surface-00"
              >
                {busy ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Plus size={15} />
                )}{" "}
                Cadastrar
              </Button>
            </form>
            {challenge && (
              <section className="space-y-2 rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4 text-sm text-yellow-100">
                <h4 className="font-bold">Guarde a prova de propriedade DNS</h4>
                <p className="text-xs">
                  Este valor aparece somente nesta sessao. Adicione o registro
                  no provedor DNS antes de testar.
                </p>
                <dl>
                  {[
                    ["Tipo", challenge.record_type],
                    ["Nome", challenge.record_name],
                    ["Valor", challenge.record_value],
                  ].map(([label, value]) => (
                    <div key={label} className="mt-2">
                      <dt className="text-xs text-stone">{label}</dt>
                      <dd className="select-all break-all font-mono text-xs">
                        {value}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}
            {!items.length ? (
              <p className="rounded-xl border border-dashed border-surface-03 p-8 text-center text-sm text-stone">
                Nenhum dominio cadastrado. Adicione o endereco da sua empresa
                acima.
              </p>
            ) : (
              <div className="space-y-3">
                {items.map((domain) => (
                  <article
                    key={domain.id}
                    className="flex flex-col gap-3 rounded-xl border border-surface-03 bg-surface-02 p-4 lg:flex-row lg:items-center lg:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="break-all font-bold text-cream">
                          {domain.hostname}
                        </h4>
                        <DomainStatusBadge status={domain.status} />
                        {domain.is_primary && (
                          <span className="text-xs text-gold">Principal</span>
                        )}
                      </div>
                      <DomainCertificateStatus domain={domain} />
                      {domain.error_message && (
                        <p className="mt-2 text-xs text-red-300">
                          {domain.error_message}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {[
                        "pending",
                        "awaiting_dns",
                        "verifying",
                        "dns_error",
                      ].includes(domain.status) && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busy || !canManage}
                          onClick={() => void act(domain, "verify")}
                        >
                          Testar DNS
                        </Button>
                      )}
                      {[
                        "pending",
                        "awaiting_dns",
                        "dns_error",
                        "verified",
                        "active",
                        "ssl_error",
                      ].includes(domain.status) && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busy}
                          onClick={() => setSelected(domain)}
                        >
                          Configurar HTTPS
                        </Button>
                      )}
                      {domain.status === "verified" && (
                        <Button
                          size="sm"
                          disabled={
                            busy || !canManage ||
                            domain.ssl_status !== "active" ||
                            !domain.ssl_expires_at ||
                            !(Date.parse(domain.ssl_expires_at) > Date.now())
                          }
                          title="Requer DNS verificado e certificado HTTPS valido"
                          onClick={() => void act(domain, "activate")}
                        >
                          Ativar dominio
                        </Button>
                      )}
                      {domain.status === "active" && (
                        <Button asChild variant="outline" size="sm">
                          <a
                            href={`https://${domain.hostname}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Abrir loja
                          </a>
                        </Button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )
      )}
      {selected && (
        <DomainCertificateDialog
          domain={selected}
          api={companyDomainsApi}
          canRequest={canManage}
          onClose={() => setSelected(null)}
          onChanged={(summary) =>
            setItems((current) =>
              current.map((item) =>
                item.id === summary.domain_id
                  ? {
                      ...item,
                      ssl_status:
                        summary.ssl_status as ApiPlatformTenantDomain["ssl_status"],
                      ssl_issued_at: summary.ssl_issued_at,
                      ssl_expires_at: summary.ssl_expires_at,
                    }
                  : item,
              ),
            )
          }
        />
      )}
    </section>
  );
}
