import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleAlert,
  CloudCog,
  Globe2,
  KeyRound,
  Loader2,
  LockKeyhole,
  RefreshCw,
  RotateCcw,
  ServerCog,
  ShieldCheck,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  platformSettingsApi,
  type ApiPlatformJwtSecretState,
  type ApiPlatformRolloutCategory,
  type ApiPlatformRolloutFlag,
  type ApiPlatformSettings,
  type ApiPlatformSettingsAlertSeverity,
  type ApiPlatformSettingsStatus,
} from "@/lib/api";

export function platformSettingsStatusLabel(status: ApiPlatformSettingsStatus): string {
  if (status === "critical") return "Critico";
  if (status === "attention") return "Requer atencao";
  return "Saudavel";
}

export function platformJwtSecretStateLabel(state: ApiPlatformJwtSecretState): string {
  if (state === "missing") return "Ausente";
  if (state === "default") return "Padrao inseguro";
  return "Configurado";
}

export function platformRolloutCategoryLabel(category: string): string {
  if (category === "isolation") return "Isolamento";
  if (category === "security") return "Seguranca";
  if (category === "access") return "Acesso";
  if (category === "runtime") return "Runtime";
  return "Outros";
}

export function groupPlatformRolloutFlags(
  flags: ApiPlatformRolloutFlag[],
): Array<{ category: ApiPlatformRolloutCategory; flags: ApiPlatformRolloutFlag[] }> {
  const grouped = new Map<ApiPlatformRolloutCategory, ApiPlatformRolloutFlag[]>();
  flags.forEach((flag) => {
    grouped.set(flag.category, [...(grouped.get(flag.category) ?? []), flag]);
  });
  return [...grouped].map(([category, categoryFlags]) => ({ category, flags: categoryFlags }));
}

function statusTone(status: ApiPlatformSettingsStatus): string {
  if (status === "critical") return "border-red-500/35 bg-red-500/10 text-red-200";
  if (status === "attention") return "border-yellow-500/35 bg-yellow-500/10 text-yellow-100";
  return "border-green-500/35 bg-green-500/10 text-green-200";
}

function alertTone(severity: ApiPlatformSettingsAlertSeverity): string {
  if (severity === "critical") return "border-red-500/35 bg-red-500/10 text-red-100";
  if (severity === "warning") return "border-yellow-500/35 bg-yellow-500/10 text-yellow-50";
  return "border-blue-400/30 bg-blue-400/10 text-blue-100";
}

function jwtTone(state: ApiPlatformJwtSecretState): string {
  return state === "configured"
    ? "border-green-500/30 bg-green-500/10 text-green-200"
    : "border-red-500/35 bg-red-500/10 text-red-200";
}

function StateBadge({ enabled, trueLabel = "Ativo", falseLabel = "Inativo" }: {
  enabled: boolean;
  trueLabel?: string;
  falseLabel?: string;
}) {
  return (
    <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-bold ${
      enabled
        ? "border-green-500/30 bg-green-500/10 text-green-200"
        : "border-stone/25 bg-surface-03 text-stone"
    }`}>
      {enabled ? trueLabel : falseLabel}
    </span>
  );
}

function SettingRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-11 items-center justify-between gap-4 border-b border-surface-03 py-2.5 last:border-b-0">
      <dt className="text-sm text-stone">{label}</dt>
      <dd className="min-w-0 text-right text-sm font-bold text-cream">{children}</dd>
    </div>
  );
}

function InitialLoading() {
  return (
    <section className="flex min-h-64 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02">
      <div className="text-center text-stone">
        <Loader2 size={28} aria-label="Carregando configuracoes" className="mx-auto animate-spin text-gold" />
        <p className="mt-3 text-sm">Carregando configuracoes da plataforma...</p>
      </div>
    </section>
  );
}

export default function PlatformSettings() {
  const [settings, setSettings] = useState<ApiPlatformSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const result = await platformSettingsApi.get();
      if (requestId.current === currentRequest) setSettings(result);
    } catch (loadError) {
      if (requestId.current === currentRequest) {
        setError(loadError instanceof Error
          ? loadError.message
          : "Nao foi possivel carregar as configuracoes da plataforma.");
      }
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    return () => { requestId.current += 1; };
  }, [load]);

  const rolloutGroups = useMemo(
    () => groupPlatformRolloutFlags(settings?.rollout_flags ?? []),
    [settings?.rollout_flags],
  );

  if (loading && !settings) return <InitialLoading />;

  if (error && !settings) {
    return (
      <section role="alert" className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-center text-red-100">
        <CircleAlert size={32} className="mx-auto" />
        <h2 className="mt-3 font-black">Falha ao carregar configuracoes</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm text-red-100/80">{error}</p>
        <Button type="button" variant="outline" onClick={() => void load()} className="mt-5 gap-2">
          <RefreshCw size={15} /> Tentar novamente
        </Button>
      </section>
    );
  }

  if (!settings) {
    return (
      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-8 text-center">
        <CloudCog size={34} className="mx-auto text-stone" />
        <h2 className="mt-3 font-black text-cream">Configuracoes indisponiveis</h2>
        <p className="mt-2 text-sm text-stone">A API nao retornou uma configuracao consultavel.</p>
        <Button type="button" variant="outline" onClick={() => void load()} className="mt-5 gap-2">
          <RefreshCw size={15} /> Consultar novamente
        </Button>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="rounded-xl border border-gold/25 bg-gold/10 p-2.5 text-gold">
            <ServerCog size={20} />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-wide text-stone">Estado da configuracao</p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-2 py-1 text-xs font-black ${statusTone(settings.status)}`}>
                {platformSettingsStatusLabel(settings.status)}
              </span>
              <span className="text-xs text-stone">Origem: ambiente do backend</span>
            </div>
          </div>
        </div>
        <Button type="button" variant="outline" onClick={() => void load()} disabled={loading} className="gap-2 border-surface-03 bg-surface-01 text-cream">
          {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Atualizar
        </Button>
      </section>

      {error && (
        <div role="alert" className="flex flex-col gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100 sm:flex-row sm:items-center sm:justify-between">
          <span>{error}</span>
          <Button type="button" variant="outline" size="sm" onClick={() => void load()} className="gap-2">
            <RefreshCw size={14} /> Tentar novamente
          </Button>
        </div>
      )}

      <section className="rounded-2xl border border-yellow-500/25 bg-yellow-500/10 p-4">
        <div className="flex items-start gap-3">
          <LockKeyhole size={19} className="mt-0.5 shrink-0 text-yellow-100" />
          <div>
            <h2 className="font-black text-yellow-50">Consulta somente leitura</h2>
            <p className="mt-1 text-sm leading-relaxed text-yellow-50/75">
              Nenhuma alteracao e executada nesta tela. As configuracoes sao carregadas do ambiente do backend;
              ajustes devem passar pelo processo de deploy{settings.restart_required ? " e exigem reinicio do servico" : ""}.
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle size={18} className="text-gold" />
          <h2 className="font-black text-cream">Alertas de configuracao</h2>
          <span className="rounded-full border border-surface-03 px-2 py-0.5 text-xs text-stone">{settings.alerts.length}</span>
        </div>
        {settings.alerts.length ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {settings.alerts.map((alert) => (
              <article key={alert.key} className={`rounded-xl border p-4 ${alertTone(alert.severity)}`}>
                <div className="flex items-start gap-3">
                  {alert.severity === "critical"
                    ? <CircleAlert size={18} className="mt-0.5 shrink-0" />
                    : <AlertTriangle size={18} className="mt-0.5 shrink-0" />}
                  <div>
                    <p className="font-black">{alert.title}</p>
                    <p className="mt-1 text-sm opacity-80">{alert.description}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-xl border border-green-500/25 bg-green-500/10 p-4 text-green-100">
            <CheckCircle2 size={19} />
            <p className="text-sm font-bold">Nenhum alerta de configuracao foi informado pelo backend.</p>
          </div>
        )}
      </section>

      <div className="grid gap-4 xl:grid-cols-3">
        <section className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
          <h2 className="flex items-center gap-2 font-black text-cream"><ServerCog size={18} className="text-gold" /> Aplicacao</h2>
          <dl className="mt-4">
            <SettingRow label="Marca">{settings.application.platform_brand_name || "Nao informada"}</SettingRow>
            <SettingRow label="Aplicacao">{settings.application.app_name || "Nao informada"}</SettingRow>
            <SettingRow label="Versao">{settings.application.app_version || "Nao informada"}</SettingRow>
            <SettingRow label="Debug"><StateBadge enabled={settings.application.debug} trueLabel="Ligado" falseLabel="Desligado" /></SettingRow>
          </dl>
        </section>

        <section className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
          <h2 className="flex items-center gap-2 font-black text-cream"><ShieldCheck size={18} className="text-gold" /> Seguranca</h2>
          <dl className="mt-4">
            <SettingRow label="Segredo JWT">
              <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-bold ${jwtTone(settings.security.jwt_secret_state)}`}>
                {platformJwtSecretStateLabel(settings.security.jwt_secret_state)}
              </span>
            </SettingRow>
            <SettingRow label="RBAC da plataforma"><StateBadge enabled={settings.security.platform_rbac_enabled} /></SettingRow>
            <SettingRow label="Autenticacao multiempresa"><StateBadge enabled={settings.security.multi_tenant_auth_enabled} /></SettingRow>
          </dl>
          <p className="mt-3 flex items-center gap-2 text-xs text-stone"><KeyRound size={13} /> O valor do segredo JWT nunca e retornado.</p>
        </section>

        <section className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
          <h2 className="flex items-center gap-2 font-black text-cream"><Globe2 size={18} className="text-gold" /> Dominios e proxy</h2>
          <dl className="mt-4">
            <SettingRow label="Resolucao por dominio"><StateBadge enabled={settings.domains.enabled} /></SettingRow>
            <SettingRow label="Headers de proxy"><StateBadge enabled={settings.domains.trust_proxy_headers} trueLabel="Confiaveis" falseLabel="Ignorados" /></SettingRow>
            <SettingRow label="Hostnames validos">{settings.domains.platform_hostname_count}</SettingRow>
            <SettingRow label="Hostnames invalidos">{settings.domains.invalid_platform_hostname_count}</SettingRow>
            <SettingRow label="Proxies confiaveis">{settings.domains.trusted_proxy_count}</SettingRow>
            <SettingRow label="Proxies invalidos">{settings.domains.invalid_trusted_proxy_count}</SettingRow>
          </dl>
          <div className="mt-4 border-t border-surface-03 pt-4">
            <p className="text-xs font-bold uppercase tracking-wide text-stone">Hostnames da plataforma</p>
            {settings.domains.platform_hostnames.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {settings.domains.platform_hostnames.map((hostname) => (
                  <span key={hostname} className="rounded-full border border-surface-03 bg-surface-01 px-2.5 py-1 text-xs text-cream">{hostname}</span>
                ))}
              </div>
            ) : <p className="mt-2 text-sm text-stone">Nenhum hostname valido configurado.</p>}
          </div>
          <p className="mt-3 text-xs text-stone">Os enderecos IP e CIDRs dos proxies permanecem protegidos.</p>
        </section>
      </div>

      <section className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
        <div className="flex items-center gap-2">
          <RotateCcw size={18} className="text-gold" />
          <div>
            <h2 className="font-black text-cream">Rollout multiempresa</h2>
            <p className="mt-1 text-xs text-stone">Flags allowlisted pelo backend. O estado exibido nao altera o ambiente.</p>
          </div>
        </div>
        {rolloutGroups.length ? (
          <div className="mt-5 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {rolloutGroups.map((group) => (
              <article key={group.category} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
                <h3 className="text-xs font-black uppercase tracking-wide text-gold">
                  {platformRolloutCategoryLabel(group.category)}
                </h3>
                <div className="mt-3 space-y-2">
                  {group.flags.map((flag) => (
                    <div key={flag.key} className="flex items-center justify-between gap-3 border-b border-surface-03 pb-2 last:border-b-0 last:pb-0">
                      <span className="min-w-0 text-sm text-cream" title={flag.key}>{flag.label}</span>
                      <StateBadge enabled={flag.enabled} />
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="mt-5 rounded-xl border border-surface-03 bg-surface-01 p-6 text-center text-sm text-stone">
            Nenhuma flag de rollout foi publicada pela API.
          </div>
        )}
      </section>
    </div>
  );
}
