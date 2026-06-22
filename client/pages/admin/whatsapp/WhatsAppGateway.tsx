import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  Plus,
  Power,
  QrCode,
  RefreshCw,
  RotateCcw,
  Server,
  ShieldCheck,
  Smartphone,
  type LucideIcon,
} from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import {
  whatsappGatewayApi,
  type ApiWhatsAppGatewayInstance,
  type ApiWhatsAppGatewayLog,
  type ApiWhatsAppGatewayOverview,
  type ApiWhatsAppGatewayUpdateStatus,
} from "@/lib/api";

type Tab = "overview" | "instances" | "logs" | "updates";

const tabs: AdminPageTab<Tab>[] = [
  { id: "overview", label: "Visao Geral", icon: Activity },
  { id: "instances", label: "Instancias", icon: Smartphone },
  { id: "logs", label: "Logs Tecnicos", icon: Server },
  { id: "updates", label: "Atualizacoes", icon: ShieldCheck },
];

function fmtDate(value?: string | null) {
  if (!value) return "-";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return "-";
  }
}

function toDisplayText(value: unknown, fallback = "-") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const text = value.map((item) => toDisplayText(item, "")).filter(Boolean).join(", ");
    return text || fallback;
  }
  if (typeof value === "object") {
    const objectValue = value as Record<string, unknown>;
    const candidate =
      objectValue.message ?? objectValue.detail ?? objectValue.error ?? objectValue.status ?? objectValue.name ?? objectValue.title;
    if (candidate !== undefined && candidate !== value) return toDisplayText(candidate, fallback);
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

function toErrorMessage(err: unknown, fallback: string) {
  if (err instanceof Error) return toDisplayText(err.message, fallback);
  return toDisplayText(err, fallback);
}

function statusClass(rawStatus: unknown) {
  const status = toDisplayText(rawStatus, "unknown");
  if (["connected", "installed", "success"].includes(status)) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (["created", "runtime_pending", "info"].includes(status)) return "border-sky-500/30 bg-sky-500/10 text-sky-300";
  if (["qr_required", "warning"].includes(status)) return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  return "border-red-500/30 bg-red-500/10 text-red-300";
}

function StatusBadge({ status }: { status: unknown }) {
  const label = toDisplayText(status, "unknown");
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClass(label)}`}>
      {label.replace(/_/g, " ")}
    </span>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: unknown;
  icon: LucideIcon;
}) {
  return (
    <div className="rounded-lg border border-surface-03 bg-surface-02 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-stone">{label}</p>
        <Icon size={17} className="text-gold" />
      </div>
      <p className="mt-3 text-2xl font-black text-cream">{toDisplayText(value)}</p>
    </div>
  );
}

function GatewayLoading() {
  return (
    <div className="flex min-h-[18rem] items-center justify-center rounded-lg border border-surface-03 bg-surface-02">
      <Loader2 className="mr-2 h-5 w-5 animate-spin text-gold" />
      <span className="text-sm font-semibold text-stone">Carregando Gateway</span>
    </div>
  );
}

function shouldStartConnectionForQr(status: unknown) {
  const normalized = toDisplayText(status, "").toLowerCase();
  return !["connecting", "qr_required", "connected"].includes(normalized);
}

function shouldStopQrPolling(status: unknown) {
  const normalized = toDisplayText(status, "").toLowerCase();
  return ["connected", "error", "runtime_offline", "logged_out", "package_missing", "unauthorized"].includes(normalized);
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function WhatsAppGateway() {
  const [tab, setTab] = useState<Tab>("overview");
  const [overview, setOverview] = useState<ApiWhatsAppGatewayOverview | null>(null);
  const [instances, setInstances] = useState<ApiWhatsAppGatewayInstance[]>([]);
  const [logs, setLogs] = useState<ApiWhatsAppGatewayLog[]>([]);
  const [updates, setUpdates] = useState<ApiWhatsAppGatewayUpdateStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("Principal");
  const [phone, setPhone] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [updateAction, setUpdateAction] = useState<"check" | "confirm" | null>(null);
  const [qrPreview, setQrPreview] = useState<{
    instanceId: string;
    name: string;
    status: string;
    message: string;
    dataUrl: string | null;
  } | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [overviewData, instanceData, logData, updateData] = await Promise.all([
        whatsappGatewayApi.overview(),
        whatsappGatewayApi.listInstances(),
        whatsappGatewayApi.listLogs({ limit: 30 }),
        whatsappGatewayApi.updateStatus(),
      ]);
      setOverview(overviewData);
      setInstances(instanceData);
      setLogs(logData);
      setUpdates(updateData);
    } catch (err) {
      setError(toErrorMessage(err, "Falha ao carregar WhatsApp Gateway."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function createInstance() {
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await whatsappGatewayApi.createInstance({
        name: name.trim(),
        phone_number: phone.trim() || null,
        provider: "baileys",
      });
      setName("Principal");
      setPhone("");
      await loadAll();
      setTab("instances");
    } catch (err) {
      setError(toErrorMessage(err, "Falha ao criar instancia."));
    } finally {
      setSaving(false);
    }
  }

  async function runInstanceAction(
    instance: ApiWhatsAppGatewayInstance,
    action: "connect" | "qrcode" | "status" | "disconnect" | "restart",
  ) {
    const key = `${action}:${instance.id}`;
    setActionLoading(key);
    setError(null);
    try {
      let result =
        action === "connect"
          ? await whatsappGatewayApi.connectInstance(instance.id)
          : action === "qrcode"
            ? shouldStartConnectionForQr(instance.status)
              ? await whatsappGatewayApi.connectInstance(instance.id)
              : await whatsappGatewayApi.getQrCode(instance.id)
            : action === "status"
              ? await whatsappGatewayApi.getInstanceStatus(instance.id)
              : action === "disconnect"
                ? await whatsappGatewayApi.disconnectInstance(instance.id)
                : await whatsappGatewayApi.restartInstance(instance.id);

      setInstances((current) => current.map((item) => (item.id === instance.id ? result.instance : item)));
      if (["connect", "qrcode", "restart"].includes(action)) {
        setQrPreview({
          instanceId: instance.id,
          name: toDisplayText(instance.name, "Instancia"),
          status: toDisplayText(result.instance.status, "unknown"),
          message: toDisplayText(result.message, "Acao executada."),
          dataUrl: result.qr_code_data_url,
        });

        for (let attempt = 0; attempt < 8 && !result.qr_code_data_url && !shouldStopQrPolling(result.instance.status); attempt += 1) {
          await wait(1250);
          result = await whatsappGatewayApi.getQrCode(instance.id);
          setInstances((current) => current.map((item) => (item.id === instance.id ? result.instance : item)));
          setQrPreview({
            instanceId: instance.id,
            name: toDisplayText(instance.name, "Instancia"),
            status: toDisplayText(result.instance.status, "unknown"),
            message: toDisplayText(result.message, "Aguardando QR Code."),
            dataUrl: result.qr_code_data_url,
          });
        }
      }
      if (action === "disconnect") {
        setQrPreview((current) => (current?.instanceId === instance.id ? null : current));
      }
      await loadAll();
    } catch (err) {
      setError(toErrorMessage(err, "Falha ao executar acao da instancia."));
    } finally {
      setActionLoading(null);
    }
  }

  async function checkUpdates() {
    setUpdateAction("check");
    setError(null);
    try {
      const result = await whatsappGatewayApi.checkUpdate();
      setUpdates(result);
      await loadAll();
      setTab("updates");
    } catch (err) {
      setError(toErrorMessage(err, "Falha ao verificar atualizacao da Baileys."));
    } finally {
      setUpdateAction(null);
    }
  }

  async function confirmUpdate() {
    if (!updates?.check_id || !updates.available_version) return;
    const confirmed = window.confirm(`Confirmar atualizacao da Baileys para ${toDisplayText(updates.available_version)}?`);
    if (!confirmed) return;
    setUpdateAction("confirm");
    setError(null);
    try {
      await whatsappGatewayApi.confirmUpdate({
        check_id: updates.check_id,
        target_version: updates.available_version,
        confirm: true,
      });
      const result = await whatsappGatewayApi.updateStatus();
      setUpdates(result);
      await loadAll();
      setTab("updates");
    } catch (err) {
      setError(toErrorMessage(err, "Falha ao confirmar atualizacao da Baileys."));
    } finally {
      setUpdateAction(null);
    }
  }

  const providerStatus = toDisplayText(overview?.provider.runtime_status, "unknown");
  const updateMessage = toDisplayText(updates?.message, "Status de atualizacao indisponivel.");
  const recentLogs = useMemo(() => logs.slice(0, 12), [logs]);

  return (
    <AdminPageShell>
      <AdminPageHeader
        eyebrow="Configuracoes"
        title="WhatsApp Gateway"
        description="Conexoes, sessoes, Baileys, saude e atualizacoes"
        icon={<Server size={21} />}
        actions={
          <button
            type="button"
            onClick={loadAll}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-sm font-semibold text-cream hover:bg-surface-03 disabled:opacity-60"
          >
            {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Atualizar
          </button>
        }
      />
      <AdminPageContent>
        <AdminPageTabs<Tab> tabs={tabs} active={tab} onChange={setTab} />

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
            <AlertTriangle size={17} className="mt-0.5 shrink-0" />
            <span>{toDisplayText(error)}</span>
          </div>
        )}

        {loading ? (
          <GatewayLoading />
        ) : (
          <>
            {tab === "overview" && overview && (
              <div className="space-y-5">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <MetricCard label="Instancias" value={overview.total_instances} icon={Smartphone} />
                  <MetricCard label="Conectadas" value={overview.connected_instances} icon={CheckCircle2} />
                  <MetricCard label="Desconectadas" value={overview.disconnected_instances} icon={AlertTriangle} />
                  <MetricCard label="QR pendente" value={overview.qr_required_instances} icon={Clock3} />
                </div>

                <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                  <section className="rounded-lg border border-surface-03 bg-surface-02 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h2 className="text-base font-bold text-cream">Provider Baileys</h2>
                        <p className="mt-1 text-sm text-stone">{toDisplayText(overview.provider.package_name)}</p>
                      </div>
                      <StatusBadge status={providerStatus} />
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div>
                        <p className="text-xs text-stone">Instalada</p>
                        <p className="mt-1 font-semibold text-cream">{overview.provider.installed ? "Sim" : "Nao"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-stone">Versao</p>
                        <p className="mt-1 font-semibold text-cream">{toDisplayText(overview.provider.installed_version)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-stone">Atualizacao em producao</p>
                        <p className="mt-1 font-semibold text-cream">
                          {overview.provider.production_auto_update_enabled ? "Ativa" : "Desativada"}
                        </p>
                      </div>
                    </div>
                  </section>

                  <section className="rounded-lg border border-surface-03 bg-surface-02 p-4">
                    <h2 className="text-base font-bold text-cream">Agendamento</h2>
                    <div className="mt-4 space-y-3 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-stone">Health check</span>
                        <span className="font-semibold text-cream">
                          {toDisplayText(overview.scheduler.morning_check_time)} / {toDisplayText(overview.scheduler.evening_check_time)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-stone">Verificar atualizacao</span>
                        <span className="font-semibold text-cream">
                          {overview.scheduler.auto_update_check_enabled ? "Ativo" : "Inativo"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-stone">Confirmacao producao</span>
                        <span className="font-semibold text-cream">Obrigatoria</span>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            )}

            {tab === "instances" && (
              <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
                <section className="rounded-lg border border-surface-03 bg-surface-02 p-4">
                  <h2 className="text-base font-bold text-cream">Nova instancia</h2>
                  <div className="mt-4 space-y-3">
                    <label className="block">
                      <span className="text-xs font-semibold text-stone">Nome</span>
                      <input
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        className="mt-1 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold"
                      />
                    </label>
                    <label className="block">
                      <span className="text-xs font-semibold text-stone">Numero</span>
                      <input
                        value={phone}
                        onChange={(event) => setPhone(event.target.value)}
                        placeholder="5511999999999"
                        className="mt-1 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={createInstance}
                      disabled={saving || !name.trim()}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-bold text-black hover:bg-gold/90 disabled:opacity-60"
                    >
                      {saving ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                      Criar instancia
                    </button>
                  </div>
                  {qrPreview && (
                    <div className="mt-4 rounded-lg border border-surface-03 bg-surface-01 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold text-cream">{qrPreview.name}</p>
                          <p className="mt-1 text-xs text-stone">{qrPreview.message}</p>
                        </div>
                        <StatusBadge status={qrPreview.status} />
                      </div>
                      <div className="mt-3 flex min-h-[13rem] items-center justify-center rounded-lg bg-white p-3">
                        {qrPreview.dataUrl ? (
                          <img src={qrPreview.dataUrl} alt="QR Code WhatsApp" className="h-48 w-48" />
                        ) : (
                          <div className="px-4 text-center text-sm font-semibold text-neutral-700">
                            QR Code ainda nao disponivel
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </section>

                <section className="overflow-hidden rounded-lg border border-surface-03 bg-surface-02">
                  <div className="border-b border-surface-03 px-4 py-3">
                    <h2 className="text-base font-bold text-cream">Instancias</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[980px] text-left text-sm">
                      <thead className="bg-surface-01 text-xs uppercase tracking-wide text-stone">
                        <tr>
                          <th className="px-4 py-3">Nome</th>
                          <th className="px-4 py-3">Numero</th>
                          <th className="px-4 py-3">Provider</th>
                          <th className="px-4 py-3">Status</th>
                          <th className="px-4 py-3">Criada em</th>
                          <th className="px-4 py-3">Acoes</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {instances.map((instance) => (
                          <tr key={instance.id} className="text-stone">
                            <td className="px-4 py-3 font-semibold text-cream">{toDisplayText(instance.name)}</td>
                            <td className="px-4 py-3">{toDisplayText(instance.phone_number)}</td>
                            <td className="px-4 py-3">{toDisplayText(instance.provider)}</td>
                            <td className="px-4 py-3"><StatusBadge status={instance.status} /></td>
                            <td className="px-4 py-3">{fmtDate(instance.created_at)}</td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  title="Conectar"
                                  onClick={() => runInstanceAction(instance, "connect")}
                                  disabled={Boolean(actionLoading)}
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-surface-03 bg-surface-01 text-cream hover:border-gold disabled:opacity-50"
                                >
                                  {actionLoading === `connect:${instance.id}` ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />}
                                </button>
                                <button
                                  type="button"
                                  title="QR Code"
                                  onClick={() => runInstanceAction(instance, "qrcode")}
                                  disabled={Boolean(actionLoading)}
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-surface-03 bg-surface-01 text-cream hover:border-gold disabled:opacity-50"
                                >
                                  {actionLoading === `qrcode:${instance.id}` ? <Loader2 size={14} className="animate-spin" /> : <QrCode size={14} />}
                                </button>
                                <button
                                  type="button"
                                  title="Atualizar status"
                                  onClick={() => runInstanceAction(instance, "status")}
                                  disabled={Boolean(actionLoading)}
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-surface-03 bg-surface-01 text-cream hover:border-gold disabled:opacity-50"
                                >
                                  {actionLoading === `status:${instance.id}` ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                                </button>
                                <button
                                  type="button"
                                  title="Reiniciar"
                                  onClick={() => runInstanceAction(instance, "restart")}
                                  disabled={Boolean(actionLoading)}
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-surface-03 bg-surface-01 text-cream hover:border-gold disabled:opacity-50"
                                >
                                  {actionLoading === `restart:${instance.id}` ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                                </button>
                                <button
                                  type="button"
                                  title="Desconectar"
                                  onClick={() => runInstanceAction(instance, "disconnect")}
                                  disabled={Boolean(actionLoading)}
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-200 hover:bg-red-500/20 disabled:opacity-50"
                                >
                                  {actionLoading === `disconnect:${instance.id}` ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                        {instances.length === 0 && (
                          <tr>
                            <td className="px-4 py-8 text-center text-stone" colSpan={6}>
                              Nenhuma instancia criada
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            )}

            {tab === "logs" && (
              <section className="overflow-hidden rounded-lg border border-surface-03 bg-surface-02">
                <div className="border-b border-surface-03 px-4 py-3">
                  <h2 className="text-base font-bold text-cream">Logs tecnicos</h2>
                </div>
                <div className="divide-y divide-surface-03">
                  {recentLogs.map((log) => (
                    <div key={log.id} className="grid gap-2 px-4 py-3 md:grid-cols-[10rem_8rem_1fr] md:items-center">
                      <span className="text-xs text-stone">{fmtDate(log.created_at)}</span>
                      <StatusBadge status={log.status} />
                      <div>
                        <p className="text-sm font-semibold text-cream">{toDisplayText(log.action)}</p>
                        <p className="text-sm text-stone">{toDisplayText(log.message)}</p>
                      </div>
                    </div>
                  ))}
                  {recentLogs.length === 0 && (
                    <div className="px-4 py-8 text-center text-stone">Sem logs registrados</div>
                  )}
                </div>
              </section>
            )}

            {tab === "updates" && (
              <section className="rounded-lg border border-surface-03 bg-surface-02 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-bold text-cream">Baileys</h2>
                    <p className="mt-1 text-sm text-stone">{toDisplayText(updates?.package_name, "@whiskeysockets/baileys")}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={updates?.installed ? "installed" : "package_missing"} />
                    <button
                      type="button"
                      onClick={checkUpdates}
                      disabled={Boolean(updateAction)}
                      className="inline-flex h-9 items-center gap-2 rounded-lg border border-surface-03 bg-surface-01 px-3 text-xs font-semibold text-cream hover:border-gold disabled:opacity-60"
                    >
                      {updateAction === "check" ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                      Verificar
                    </button>
                    <button
                      type="button"
                      onClick={confirmUpdate}
                      disabled={Boolean(updateAction) || !updates?.confirmation_available}
                      className="inline-flex h-9 items-center gap-2 rounded-lg bg-gold px-3 text-xs font-bold text-black hover:bg-gold/90 disabled:opacity-50"
                    >
                      {updateAction === "confirm" ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
                      Confirmar
                    </button>
                  </div>
                </div>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MetricCard label="Instalada" value={updates?.installed ? "Sim" : "Nao"} icon={CheckCircle2} />
                  <MetricCard label="Versao atual" value={updates?.installed_version} icon={Server} />
                  <MetricCard label="Disponivel" value={updates?.available_version} icon={RefreshCw} />
                  <MetricCard label="Confirmacao" value={updates?.confirmation_required ? "Manual" : "Livre"} icon={ShieldCheck} />
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border border-surface-03 bg-surface-01 p-3">
                    <p className="text-xs text-stone">Ultima verificacao</p>
                    <p className="mt-1 text-sm font-semibold text-cream">{fmtDate(updates?.last_checked_at)}</p>
                  </div>
                  <div className="rounded-lg border border-surface-03 bg-surface-01 p-3">
                    <p className="text-xs text-stone">Tipo</p>
                    <p className="mt-1 text-sm font-semibold text-cream">{toDisplayText(updates?.update_type)}</p>
                  </div>
                  <div className="rounded-lg border border-surface-03 bg-surface-01 p-3">
                    <p className="text-xs text-stone">Risco</p>
                    <p className="mt-1 text-sm font-semibold text-cream">{toDisplayText(updates?.risk_level)}</p>
                  </div>
                </div>
                <div className="mt-4 rounded-lg border border-surface-03 bg-surface-01 p-3 text-sm text-stone">
                  {updateMessage}
                </div>
              </section>
            )}
          </>
        )}
      </AdminPageContent>
    </AdminPageShell>
  );
}
