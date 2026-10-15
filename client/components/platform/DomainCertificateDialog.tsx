import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  platformDomainsApi,
  type ApiPlatformDomainCertificate,
  type ApiPlatformTenantDomain,
} from "@/lib/api";

const STATUS: Record<string, string> = {
  pending: "Aguardando configuracao HTTPS",
  queued: "Emissao na fila",
  running: "Emissao em andamento",
  active: "HTTPS ativo",
  succeeded: "Certificado instalado",
  failed: "Falha na emissao",
  error: "Erro HTTPS",
  cancelled: "Solicitacao cancelada",
};

export function DomainCertificateStatus({
  domain,
}: {
  domain: { ssl_status?: string | null; ssl_expires_at?: string | null };
}) {
  const expired =
    domain.ssl_expires_at &&
    new Date(domain.ssl_expires_at).getTime() <= Date.now();
  return (
    <p
      className={`mt-2 text-xs ${expired || ["failed", "error"].includes(domain.ssl_status || "") ? "text-red-300" : "text-stone"}`}
    >
      {expired
        ? "Certificado vencido"
        : STATUS[domain.ssl_status || "pending"] || domain.ssl_status}
      {domain.ssl_expires_at && (
        <>
          {" "}
          · Validade: {new Date(domain.ssl_expires_at).toLocaleString("pt-BR")}
        </>
      )}
    </p>
  );
}

export function DomainCertificateDialog({
  domain,
  onClose,
  onChanged,
  api = platformDomainsApi,
  canRequest = true,
}: {
  domain: ApiPlatformTenantDomain;
  onClose: () => void;
  onChanged: (summary: ApiPlatformDomainCertificate) => void;
  api?: Pick<typeof platformDomainsApi, "certificate" | "requestCertificate">;
  canRequest?: boolean;
}) {
  const [summary, setSummary] = useState<ApiPlatformDomainCertificate | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [accepted, setAccepted] = useState(false);
  // Preserve the same key after an ambiguous network failure; a confirmed result ends the attempt.
  const attempt = useRef<{ email: string; key: string } | null>(null);
  const changed = useRef(onChanged);
  changed.current = onChanged;
  const alive = useRef(true);
  const pending =
    summary?.job?.status === "queued" || summary?.job?.status === "running";

  const load = useCallback(async () => {
    try {
      const result = await api.certificate(domain.id);
      if (!alive.current) return;
      setSummary(result);
      setError("");
      if (result.job || result.ssl_status === "active") attempt.current = null;
      changed.current(result);
    } catch (err) {
      if (alive.current)
        setError(
          err instanceof Error
            ? err.message
            : "Nao foi possivel consultar o HTTPS.",
        );
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [domain.id, api]);

  useEffect(() => {
    alive.current = true;
    void load();
    return () => {
      alive.current = false;
    };
  }, [load]);

  useEffect(() => {
    if (!pending) return;
    let refreshing = false;
    const timer = window.setInterval(async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        await load();
      } finally {
        refreshing = false;
      }
    }, 5000);
    return () => window.clearInterval(timer);
  }, [pending, load]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canRequest || !accepted || !summary?.available || pending || saving)
      return;
    setSaving(true);
    setError("");
    try {
      const normalizedEmail = email.trim();
      if (!attempt.current || attempt.current.email !== normalizedEmail) {
        attempt.current = { email: normalizedEmail, key: crypto.randomUUID() };
      }
      const result = await api.requestCertificate(
        domain.id,
        { email: normalizedEmail, accept_terms: true },
        attempt.current.key,
      );
      if (!alive.current) return;
      attempt.current = null;
      setSummary(result);
      changed.current(result);
    } catch (err) {
      if (alive.current)
        setError(
          err instanceof Error
            ? err.message
            : "Nao foi possivel solicitar o HTTPS.",
        );
    } finally {
      if (alive.current) setSaving(false);
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !saving) onClose();
      }}
    >
      <DialogContent className="border-surface-03 bg-surface-02 text-cream">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck size={20} /> Configurar HTTPS
          </DialogTitle>
          <DialogDescription className="text-stone">
            Acompanhe a emissao e a validade do certificado deste dominio.
          </DialogDescription>
        </DialogHeader>
        <label className="space-y-2 text-sm">
          <span>Dominio cadastrado</span>
          <Input
            readOnly
            value={domain.hostname}
            className="border-surface-03 bg-surface-01"
          />
        </label>
        {loading && (
          <div
            role="status"
            className="flex items-center gap-2 text-sm text-stone"
          >
            <Loader2 size={16} className="animate-spin" /> Consultando HTTPS...
          </div>
        )}
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"
          >
            {error}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void load()}
            >
              Consultar novamente
            </Button>
          </div>
        )}
        {summary && (
          <>
            {!!summary.dns_targets?.length && (
              <section className="space-y-2 rounded-lg border border-surface-03 bg-surface-01 p-3 text-sm">
                <h3 className="font-bold">Apontamento DNS</h3>
                <p className="text-xs text-stone">
                  No provedor DNS, aponte {domain.hostname} para os enderecos da
                  plataforma. Remova apontamentos A/AAAA conflitantes e mantenha
                  a prova TXT de propriedade.
                </p>
                <div className="space-y-1">
                  {summary.dns_targets.map((target) => (
                    <p key={target} className="break-all font-mono text-xs">
                      <strong>{target.includes(":") ? "AAAA" : "A"}</strong> ·{" "}
                      {target}
                    </p>
                  ))}
                </div>
              </section>
            )}
            <div
              className="rounded-lg border border-surface-03 bg-surface-01 p-3"
              aria-live="polite"
            >
              <DomainCertificateStatus domain={summary} />
              {summary.ssl_issued_at && (
                <p className="mt-2 text-xs text-stone">
                  Emitido em{" "}
                  {new Date(summary.ssl_issued_at).toLocaleString("pt-BR")}
                </p>
              )}
              {summary.job && (
                <p className="mt-2 text-sm">
                  {STATUS[summary.job.status]}
                  {pending && (
                    <Loader2 size={14} className="ml-2 inline animate-spin" />
                  )}
                </p>
              )}
              {summary.job?.error_message && (
                <p className="mt-2 text-sm text-red-300">
                  {summary.job.error_message}
                </p>
              )}
              {!summary.job && summary.ssl_status !== "active" && (
                <p className="mt-2 text-xs text-stone">
                  Nenhuma solicitacao registrada.
                </p>
              )}
            </div>
            {!summary.available && (
              <p role="status" className="text-sm text-yellow-200">
                {summary.unavailable_reason ||
                  "A emissao automatica esta temporariamente indisponivel. Tente novamente mais tarde ou contate o suporte."}
              </p>
            )}
            {!["verified", "active"].includes(domain.status) && (
              <p className="text-sm text-yellow-200">
                Configure o TXT de propriedade e o apontamento DNS. Depois use
                Testar DNS antes de solicitar HTTPS.
              </p>
            )}
            {canRequest &&
              summary.available &&
              ["verified", "active"].includes(domain.status) &&
              !pending && (
                <form
                  onSubmit={(event) => void submit(event)}
                  className="space-y-4"
                >
                  <label className="block space-y-2 text-sm">
                    <span>Email de contato do certificado</span>
                    <Input
                      required
                      type="email"
                      maxLength={254}
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      disabled={saving}
                      autoComplete="email"
                      className="border-surface-03 bg-surface-01"
                    />
                  </label>
                  <label className="flex items-start gap-3 text-sm text-stone">
                    <input
                      type="checkbox"
                      required
                      checked={accepted}
                      onChange={(event) => setAccepted(event.target.checked)}
                      disabled={saving}
                      className="mt-1 accent-orange-500"
                    />
                    <span>
                      Aceito os{" "}
                      <a
                        href="https://letsencrypt.org/repository/"
                        target="_blank"
                        rel="noreferrer"
                        className="text-gold underline"
                      >
                        termos do Let's Encrypt
                      </a>{" "}
                      para emissao deste certificado.
                    </span>
                  </label>
                  <p className="text-xs text-stone">
                    O DNS sera conferido novamente. O dominio so estara pronto
                    para publicacao apos a confirmacao do certificado servido.
                  </p>
                  <Button
                    type="submit"
                    disabled={saving || !accepted || !email.trim()}
                    className="w-full gap-2 bg-gold text-surface-00"
                  >
                    {saving && <Loader2 size={15} className="animate-spin" />}
                    {saving
                      ? "Solicitando..."
                      : summary.job?.status === "failed"
                        ? "Tentar novamente"
                        : "Solicitar HTTPS"}
                  </Button>
                </form>
              )}
          </>
        )}
        {summary && !error && (
          <Button
            type="button"
            variant="ghost"
            disabled={saving || loading}
            onClick={() => { setLoading(true); void load(); }}
          >
            Atualizar estado HTTPS
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          disabled={saving}
          onClick={onClose}
        >
          Fechar
        </Button>
      </DialogContent>
    </Dialog>
  );
}
