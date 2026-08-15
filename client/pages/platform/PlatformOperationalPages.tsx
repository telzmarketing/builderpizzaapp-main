import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  CircleAlert,
  CloudCog,
  DatabaseBackup,
  HardDrive,
  Loader2,
  MessageCircle,
  RefreshCw,
  Server,
  ShieldAlert,
  TimerReset,
  Workflow,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  platformBackupsApi,
  platformErrorsApi,
  platformGatewayApi,
  platformHealthApi,
  platformIntegrationsApi,
  platformJobsApi,
  platformStorageApi,
  type ApiPlatformBackupRuns,
  type ApiPlatformBackupsOverview,
  type ApiPlatformErrorsOverview,
  type ApiPlatformGatewayOverview,
  type ApiPlatformHealth,
  type ApiPlatformIntegrationConnection,
  type ApiPlatformIntegrationsOverview,
  type ApiPlatformJobItem,
  type ApiPlatformJobWorker,
  type ApiPlatformJobQueues,
  type ApiPlatformJobsOverview,
  type ApiPlatformOperationalPage,
  type ApiPlatformErrorItem,
  type ApiPlatformGatewayInstance,
  type ApiPlatformStorageOverview,
  type ApiPlatformTenantStorage,
} from "@/lib/api";
import { hasPlatformCapability, readPlatformPermissions } from "@/lib/platformCapabilities";

export function platformOperationalStatusLabel(status?: string | null): string {
  const labels: Record<string, string> = {
    healthy: "Saudavel",
    degraded: "Degradado",
    critical: "Critico",
    unknown: "Desconhecido",
    failed: "Falhou",
    connected: "Conectado",
    disconnected: "Desconectado",
    queued: "Na fila",
    running: "Executando",
    retrying: "Tentando novamente",
    succeeded: "Concluido",
    dead: "Interrompido",
    open: "Aberto",
    acknowledged: "Reconhecido",
    resolved: "Resolvido",
    normal: "Normal",
    warning: "Atencao",
  };
  if (!status) return "Nao informado";
  return labels[status.toLowerCase()] ?? status;
}

export function operationalFreshnessLabel(stale: boolean): string {
  return stale ? "Dados desatualizados" : "Dados atuais";
}

export function platformWorkerReactKey(
  worker: Pick<ApiPlatformJobWorker, "key" | "instance_key">,
): string {
  return JSON.stringify([worker.key, worker.instance_key]);
}

export function formatPlatformDate(value?: string | null): string {
  if (!value) return "Nao informado";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Nao informado";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function formatPlatformBytes(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value < 0) return "Nao informado";
  if (value < 1024) return `${Math.round(value)} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${units[unitIndex]}`;
}

export function formatPlatformDuration(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "Nao informado";
  if (seconds < 60) return `${Math.floor(seconds)} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h`;
  return `${Math.floor(seconds / 86400)} d`;
}

export function validatePlatformErrorNote(note: string): string {
  return note.trim().length >= 2 ? "" : "Informe uma nota com ao menos 2 caracteres para manter a acao auditavel.";
}

export interface OperationalParts<T extends Record<string, unknown>> {
  values: Partial<T>;
  errors: string[];
}

export async function loadOperationalParts<T extends Record<string, unknown>>(
  loaders: { [K in keyof T]: () => Promise<T[K]> },
): Promise<OperationalParts<T>> {
  const entries = Object.entries(loaders) as Array<[keyof T, () => Promise<T[keyof T]>]>;
  const settled = await Promise.allSettled(entries.map(([, loader]) => loader()));
  const values: Partial<T> = {};
  const errors: string[] = [];

  settled.forEach((result, index) => {
    const key = entries[index][0];
    if (result.status === "fulfilled") values[key] = result.value as T[keyof T];
    else errors.push(result.reason instanceof Error ? result.reason.message : "Falha ao consultar uma fonte operacional.");
  });

  if (Object.keys(values).length === 0) {
    throw new Error(errors[0] ?? "Nenhuma fonte operacional respondeu.");
  }
  return { values, errors };
}

interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
}

function useOperationalQuery<T>(loader: () => Promise<T>): QueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestId = useRef(0);

  const reload = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const result = await loader();
      if (currentRequest === requestId.current) setData(result);
    } catch (loadError) {
      if (currentRequest === requestId.current) {
        setError(loadError instanceof Error ? loadError.message : "Falha ao carregar o modulo operacional.");
      }
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void reload();
    return () => { requestId.current += 1; };
  }, [reload]);

  return { data, loading, error, reload };
}

function statusTone(status?: string | null): string {
  const normalized = status?.toLowerCase();
  if (["healthy", "connected", "succeeded", "resolved", "normal"].includes(normalized ?? "")) {
    return "border-green-500/30 bg-green-500/10 text-green-200";
  }
  if (["critical", "failed", "dead", "open"].includes(normalized ?? "")) {
    return "border-red-500/35 bg-red-500/10 text-red-100";
  }
  if (["degraded", "retrying", "warning", "acknowledged"].includes(normalized ?? "")) {
    return "border-yellow-500/35 bg-yellow-500/10 text-yellow-100";
  }
  return "border-surface-03 bg-surface-01 text-stone";
}

function StatusBadge({ status }: { status?: string | null }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-black ${statusTone(status)}`}>
      {platformOperationalStatusLabel(status)}
    </span>
  );
}

function MetricCard({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <article className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-stone">{label}</p>
      <p className="mt-2 text-2xl font-black text-cream">{value}</p>
      {note && <p className="mt-1 text-xs text-stone">{note}</p>}
    </article>
  );
}

function InitialLoading({ label }: { label: string }) {
  return (
    <section className="flex min-h-64 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02">
      <div className="text-center text-stone">
        <Loader2 size={30} aria-label={`Carregando ${label}`} className="mx-auto animate-spin text-gold" />
        <p className="mt-3 text-sm">Carregando {label}...</p>
      </div>
    </section>
  );
}

function BlockingState<T>({ state, label }: { state: QueryState<T>; label: string }) {
  if (state.loading && !state.data) return <InitialLoading label={label} />;
  if (state.error && !state.data) {
    return (
      <section role="alert" className="rounded-2xl border border-red-500/30 bg-red-500/10 p-7 text-center text-red-100">
        <CircleAlert size={34} className="mx-auto" />
        <h2 className="mt-3 font-black">Falha ao carregar {label}</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm text-red-100/80">{state.error}</p>
        <Button type="button" variant="outline" onClick={() => void state.reload()} className="mt-5 gap-2">
          <RefreshCw size={15} /> Tentar novamente
        </Button>
      </section>
    );
  }
  return null;
}

function OperationalToolbar({
  generatedAt,
  stale,
  status,
  loading,
  onRefresh,
}: {
  generatedAt?: string | null;
  stale?: boolean;
  status?: string | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        {status && <StatusBadge status={status} />}
        {stale !== undefined && (
          <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${
            stale ? "border-yellow-500/35 bg-yellow-500/10 text-yellow-100" : "border-surface-03 bg-surface-01 text-stone"
          }`}>
            {operationalFreshnessLabel(stale)}
          </span>
        )}
        <span className="text-xs text-stone">Atualizado em {formatPlatformDate(generatedAt)}</span>
      </div>
      <Button type="button" variant="outline" disabled={loading} onClick={onRefresh} className="gap-2 border-surface-03 bg-surface-01 text-cream">
        {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Atualizar
      </Button>
    </section>
  );
}

function WarningBanner({ messages, title = "Consulta parcial" }: { messages: string[]; title?: string }) {
  if (!messages.length) return null;
  return (
    <section role="alert" className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4 text-yellow-50">
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="mt-0.5 shrink-0" />
        <div>
          <p className="font-black">{title}</p>
          <p className="mt-1 text-sm text-yellow-50/75">
            Parte das fontes nao respondeu. Os dados disponiveis abaixo foram preservados; tente atualizar novamente.
          </p>
        </div>
      </div>
    </section>
  );
}

function RefreshError({ error }: { error: string }) {
  return error ? <WarningBanner messages={[error]} title="Falha na ultima atualizacao" /> : null;
}

function EmptyState({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-surface-03 bg-surface-02 p-8 text-center">
      <div className="mx-auto w-fit text-stone">{icon}</div>
      <h3 className="mt-3 font-black text-cream">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm text-stone">{detail}</p>
    </div>
  );
}

function SectionTitle({ icon, title, count }: { icon: ReactNode; title: string; count?: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gold">{icon}</span>
      <h2 className="font-black text-cream">{title}</h2>
      {count !== undefined && <span className="rounded-full border border-surface-03 px-2 py-0.5 text-xs text-stone">{count}</span>}
    </div>
  );
}

export function PlatformHealth() {
  const load = useCallback(() => platformHealthApi.get(), []);
  const state = useOperationalQuery<ApiPlatformHealth>(load);
  const blocking = <BlockingState state={state} label="a saude dos servicos" />;
  if (!state.data) return blocking;
  const data = state.data;

  return (
    <div className="space-y-5">
      <OperationalToolbar generatedAt={data.generated_at} stale={data.stale} status={data.status} loading={state.loading} onRefresh={() => void state.reload()} />
      <RefreshError error={state.error} />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Componentes" value={data.components.length} />
        <MetricCard label="Saudaveis" value={data.components.filter((item) => item.status === "healthy").length} />
        <MetricCard label="Degradados" value={data.components.filter((item) => item.status === "degraded").length} />
        <MetricCard label="Alertas" value={data.alerts.length} />
      </div>
      {data.alerts.length > 0 && (
        <section className="rounded-2xl border border-yellow-500/25 bg-yellow-500/10 p-4">
          <SectionTitle icon={<AlertTriangle size={18} />} title="Alertas ativos" count={data.alerts.length} />
          <ul className="mt-3 space-y-2 text-sm text-yellow-50/80">
            {data.alerts.map((alert, index) => <li key={`${index}-${alert}`} className="rounded-xl border border-yellow-500/20 p-3">{alert}</li>)}
          </ul>
        </section>
      )}
      <section className="space-y-3">
        <SectionTitle icon={<Server size={18} />} title="Componentes" count={data.components.length} />
        {data.components.length ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {data.components.map((component) => (
              <article key={component.key} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div><h3 className="font-black text-cream">{component.label}</h3><p className="mt-1 text-xs text-stone">Verificado em {formatPlatformDate(component.checked_at)}</p></div>
                  <StatusBadge status={component.status} />
                </div>
                <p className="mt-3 text-sm text-stone">Latencia: {component.latency_ms == null ? "Nao informada" : `${component.latency_ms} ms`}</p>
              </article>
            ))}
          </div>
        ) : <EmptyState icon={<Server size={30} />} title="Nenhum componente publicado" detail="A API respondeu sem componentes de saude consultaveis." />}
      </section>
    </div>
  );
}

type IntegrationParts = {
  overview: ApiPlatformIntegrationsOverview;
  connections: ApiPlatformOperationalPage<ApiPlatformIntegrationConnection>;
};

export function PlatformIntegrations() {
  const load = useCallback(() => loadOperationalParts<IntegrationParts>({
    overview: platformIntegrationsApi.overview,
    connections: () => platformIntegrationsApi.connections({ page: 1, page_size: 25 }),
  }), []);
  const state = useOperationalQuery(load);
  const blocking = <BlockingState state={state} label="as integracoes" />;
  if (!state.data) return blocking;
  const { overview, connections } = state.data.values;

  return (
    <div className="space-y-5">
      <OperationalToolbar generatedAt={overview?.generated_at} loading={state.loading} onRefresh={() => void state.reload()} />
      <WarningBanner messages={state.data.errors} /><RefreshError error={state.error} />
      {overview && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Total" value={overview.total} /><MetricCard label="Configuradas" value={overview.configured} />
        <MetricCard label="Saudaveis" value={overview.healthy} /><MetricCard label="Degradadas" value={overview.degraded} />
        <MetricCard label="Com falha" value={overview.failed} note={`${overview.unknown} sem estado confirmado`} />
      </div>}
      {overview && <section className="space-y-3"><SectionTitle icon={<CloudCog size={18} />} title="Categorias" count={overview.by_category.length} />
        {overview.by_category.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{overview.by_category.map((category) => (
          <article key={category.key} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><h3 className="font-black text-cream">{category.label}</h3><p className="mt-2 text-sm text-stone">{category.healthy} saudaveis · {category.degraded} degradadas · {category.failed} falhas · {category.unknown} desconhecidas</p></article>
        ))}</div> : <EmptyState icon={<CloudCog size={30} />} title="Nenhuma categoria" detail="Nao ha categorias de integracao publicadas." />}
      </section>}
      {connections && <section className="space-y-3"><SectionTitle icon={<Workflow size={18} />} title="Conexoes" count={connections.total} />
        {connections.items.length ? <div className="grid gap-3 lg:grid-cols-2">{connections.items.map((connection) => (
          <article key={connection.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-black text-cream">{connection.provider}</h3><p className="mt-1 text-sm text-stone">{connection.tenant.name} · {connection.category}</p></div><StatusBadge status={connection.status} /></div><p className="mt-3 text-xs text-stone">Ultima sincronizacao: {formatPlatformDate(connection.last_sync_at)} · {connection.configured ? "Configurada" : "Nao configurada"}</p></article>
        ))}</div> : <EmptyState icon={<Workflow size={30} />} title="Nenhuma conexao" detail="Nenhuma integracao configurada foi retornada pela API." />}
      </section>}
    </div>
  );
}

type JobParts = {
  overview: ApiPlatformJobsOverview;
  queues: ApiPlatformJobQueues;
  items: ApiPlatformOperationalPage<ApiPlatformJobItem>;
};

export function PlatformJobs() {
  const load = useCallback(() => loadOperationalParts<JobParts>({
    overview: platformJobsApi.overview,
    queues: platformJobsApi.queues,
    items: () => platformJobsApi.items({ page: 1, page_size: 25 }),
  }), []);
  const state = useOperationalQuery(load);
  const blocking = <BlockingState state={state} label="as filas e jobs" />;
  if (!state.data) return blocking;
  const { overview, queues, items } = state.data.values;

  return <div className="space-y-5">
    <OperationalToolbar generatedAt={overview?.generated_at ?? queues?.generated_at} loading={state.loading} onRefresh={() => void state.reload()} />
    <WarningBanner messages={state.data.errors} /><RefreshError error={state.error} />
    {overview && <><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><MetricCard label="Na fila" value={overview.queued} /><MetricCard label="Executando" value={overview.running} /><MetricCard label="Retentativas" value={overview.retrying} /><MetricCard label="Falhas" value={overview.failed} /><MetricCard label="Interrompidos" value={overview.dead} /></div>
      <section className="space-y-3"><SectionTitle icon={<TimerReset size={18} />} title="Workers" count={overview.workers.length} />{overview.workers.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{overview.workers.map((worker) => <article key={platformWorkerReactKey(worker)} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-center justify-between gap-3"><h3 className="font-black text-cream">{worker.key}</h3><StatusBadge status={worker.status} /></div><p className="mt-2 break-all text-xs text-stone">Instancia: {worker.instance_key}</p><p className="mt-1 text-xs text-stone">Heartbeat: {formatPlatformDate(worker.last_heartbeat_at)}{worker.stale ? " · desatualizado" : ""}</p></article>)}</div> : <EmptyState icon={<TimerReset size={30} />} title="Nenhum worker" detail="A API nao publicou workers consultaveis." />}</section></>}
    {queues && <section className="space-y-3"><SectionTitle icon={<Workflow size={18} />} title="Filas" count={queues.items.length} />{queues.items.length ? <div className="grid gap-3 lg:grid-cols-2">{queues.items.map((queue) => <article key={queue.key} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><h3 className="font-black text-cream">{queue.label}</h3><p className="mt-2 text-sm text-stone">{queue.queued} na fila · {queue.running} executando · {queue.retrying} retentativas · {queue.failed + queue.dead} falhas</p><p className="mt-2 text-xs text-stone">Pendente mais antigo: {formatPlatformDate(queue.oldest_pending_at)}</p></article>)}</div> : <EmptyState icon={<Workflow size={30} />} title="Nenhuma fila" detail="Nao ha filas publicadas para consulta." />}</section>}
    {items && <section className="space-y-3"><SectionTitle icon={<CheckCircle2 size={18} />} title="Jobs recentes" count={items.total} />{items.items.length ? <div className="grid gap-3 lg:grid-cols-2">{items.items.map((job) => <article key={job.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-black text-cream">{job.job_type}</h3><p className="mt-1 text-sm text-stone">{job.tenant?.name ?? "Plataforma"} · {job.queue}</p></div><StatusBadge status={job.status} /></div><p className="mt-3 text-xs text-stone">Tentativas: {job.attempts}/{job.max_attempts} · Idade: {formatPlatformDuration(job.age_seconds)} · Atualizado em {formatPlatformDate(job.updated_at)}</p></article>)}</div> : <EmptyState icon={<CheckCircle2 size={30} />} title="Nenhum job" detail="Nao ha execucoes recentes nesta consulta." />}</section>}
  </div>;
}

type GatewayParts = {
  overview: ApiPlatformGatewayOverview;
  instances: ApiPlatformOperationalPage<ApiPlatformGatewayInstance>;
};

export function PlatformGateway() {
  const load = useCallback(() => loadOperationalParts<GatewayParts>({
    overview: platformGatewayApi.overview,
    instances: () => platformGatewayApi.instances({ page: 1, page_size: 25 }),
  }), []);
  const state = useOperationalQuery(load);
  const blocking = <BlockingState state={state} label="o WhatsApp Gateway" />;
  if (!state.data) return blocking;
  const { overview, instances } = state.data.values;

  return <div className="space-y-5">
    <OperationalToolbar generatedAt={overview?.runtime.checked_at ?? overview?.last_activity_at} stale={overview?.runtime.stale} status={overview?.runtime.status} loading={state.loading} onRefresh={() => void state.reload()} />
    <WarningBanner messages={state.data.errors} /><RefreshError error={state.error} />
    {overview && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><MetricCard label="Instancias" value={overview.total_instances} /><MetricCard label="Conectadas" value={overview.connected} /><MetricCard label="Desconectadas" value={overview.disconnected} /><MetricCard label="Degradadas" value={overview.degraded} /><MetricCard label="Desconhecidas" value={overview.unknown} note={overview.runtime.version ? `Runtime ${overview.runtime.version}` : undefined} /></div>}
    {instances && <section className="space-y-3"><SectionTitle icon={<MessageCircle size={18} />} title="Instancias" count={instances.total} />{instances.items.length ? <div className="grid gap-3 lg:grid-cols-2">{instances.items.map((instance) => <article key={instance.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-black text-cream">{instance.name}</h3><p className="mt-1 text-sm text-stone">{instance.tenant.name} · {instance.provider}</p></div><StatusBadge status={instance.status} /></div><p className="mt-3 text-xs text-stone">Contato: {instance.phone_masked || "Protegido"} · Ultima atividade: {formatPlatformDate(instance.last_seen_at)}</p></article>)}</div> : <EmptyState icon={<MessageCircle size={30} />} title="Nenhuma instancia" detail="Nenhuma instancia do gateway foi retornada." />}</section>}
  </div>;
}

type ErrorParts = {
  overview: ApiPlatformErrorsOverview;
  items: ApiPlatformOperationalPage<ApiPlatformErrorItem>;
};

export function PlatformErrors() {
  const load = useCallback(() => loadOperationalParts<ErrorParts>({
    overview: platformErrorsApi.overview,
    items: () => platformErrorsApi.list({ page: 1, page_size: 25 }),
  }), []);
  const state = useOperationalQuery(load);
  const canManage = hasPlatformCapability(readPlatformPermissions(), "errors.manage");
  const [actionTarget, setActionTarget] = useState<{ id: string; action: "acknowledge" | "resolve" } | null>(null);
  const [actionNote, setActionNote] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState("");
  const [actionNotice, setActionNotice] = useState("");
  const blocking = <BlockingState state={state} label="os erros operacionais" />;
  if (!state.data) return blocking;
  const { overview, items } = state.data.values;

  const openAction = (id: string, action: "acknowledge" | "resolve") => {
    setActionTarget({ id, action });
    setActionNote("");
    setActionError("");
    setActionNotice("");
  };

  const submitAction = async () => {
    if (!actionTarget) return;
    const validationError = validatePlatformErrorNote(actionNote);
    if (validationError) {
      setActionError(validationError);
      return;
    }
    setActionLoading(true);
    setActionError("");
    setActionNotice("");
    try {
      if (actionTarget.action === "acknowledge") {
        await platformErrorsApi.acknowledge(actionTarget.id, actionNote.trim());
        setActionNotice("Ocorrencia reconhecida e registrada na auditoria.");
      } else {
        await platformErrorsApi.resolve(actionTarget.id, actionNote.trim());
        setActionNotice("Ocorrencia resolvida e registrada na auditoria.");
      }
      setActionTarget(null);
      setActionNote("");
      await state.reload();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Nao foi possivel registrar a acao.");
    } finally {
      setActionLoading(false);
    }
  };

  return <div className="space-y-5">
    <OperationalToolbar generatedAt={overview?.generated_at ?? overview?.last_seen_at} loading={state.loading} onRefresh={() => void state.reload()} />
    <WarningBanner messages={state.data.errors} /><RefreshError error={state.error} />
    {actionNotice && <div role="status" className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-sm font-bold text-green-100">{actionNotice}</div>}
    {overview && <><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Abertos" value={overview.total_open} /><MetricCard label="Criticos" value={overview.critical_open} /><MetricCard label="Reconhecidos" value={overview.acknowledged} /><MetricCard label="Resolvidos" value={overview.resolved} /></div>
      <section className="space-y-3"><SectionTitle icon={<ShieldAlert size={18} />} title="Fontes com erros abertos" count={overview.by_source.length} />{overview.by_source.length ? <div className="flex flex-wrap gap-2">{overview.by_source.map((source) => <span key={source.source} className="rounded-full border border-surface-03 bg-surface-02 px-3 py-2 text-sm text-cream">{source.source}: <strong>{source.total_open}</strong></span>)}</div> : <EmptyState icon={<CheckCircle2 size={30} />} title="Nenhuma fonte com erro aberto" detail="O resumo nao registrou ocorrencias abertas." />}</section></>}
    {items && <section className="space-y-3"><SectionTitle icon={<CircleAlert size={18} />} title="Ocorrencias" count={items.total} />{items.items.length ? <div className="grid gap-3 lg:grid-cols-2">{items.items.map((error) => <article key={error.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-black text-cream">{error.exception_type || error.error_code || "Erro operacional"}</h3><p className="mt-1 text-sm text-stone">{error.tenant?.name ?? "Plataforma"} · {error.source}</p></div><StatusBadge status={error.status} /></div><p className="mt-3 text-sm text-stone">Severidade: {error.severity} · Ocorrencias: {error.occurrence_count}</p><p className="mt-2 text-xs text-stone">Fingerprint {error.fingerprint.slice(0, 12)} · Ultima ocorrencia: {formatPlatformDate(error.last_seen_at)}</p>
      {canManage && error.status !== "resolved" && <div className="mt-4 border-t border-surface-03 pt-4">{actionTarget?.id === error.id ? <div className="space-y-3"><label className="block text-xs font-bold uppercase tracking-wide text-stone" htmlFor={`error-note-${error.id}`}>Nota obrigatoria</label><textarea id={`error-note-${error.id}`} value={actionNote} onChange={(event) => setActionNote(event.target.value)} disabled={actionLoading} rows={3} maxLength={1000} placeholder="Registre o motivo e o contexto operacional da acao" className="w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold" />{actionError && <p role="alert" className="text-sm text-red-200">{actionError}</p>}<div className="flex flex-col gap-2 sm:flex-row"><Button type="button" disabled={actionLoading} onClick={() => void submitAction()} className="gap-2 bg-gold text-surface-00">{actionLoading && <Loader2 size={15} className="animate-spin" />}{actionTarget.action === "acknowledge" ? "Confirmar reconhecimento" : "Confirmar resolucao"}</Button><Button type="button" variant="outline" disabled={actionLoading} onClick={() => { setActionTarget(null); setActionError(""); }} className="border-surface-03 bg-surface-01 text-cream">Cancelar</Button></div></div> : <div className="flex flex-col gap-2 sm:flex-row">{error.status === "open" && <Button type="button" variant="outline" onClick={() => openAction(error.id, "acknowledge")} className="border-surface-03 bg-surface-01 text-cream">Reconhecer</Button>}<Button type="button" variant="outline" onClick={() => openAction(error.id, "resolve")} className="border-surface-03 bg-surface-01 text-cream">Marcar como resolvido</Button></div>}</div>}
    </article>)}</div> : <EmptyState icon={<CheckCircle2 size={30} />} title="Nenhuma ocorrencia" detail="Nao ha erros na pagina consultada." />}</section>}
  </div>;
}

type StorageParts = {
  overview: ApiPlatformStorageOverview;
  tenants: ApiPlatformOperationalPage<ApiPlatformTenantStorage>;
};

export function PlatformStorage() {
  const load = useCallback(() => loadOperationalParts<StorageParts>({
    overview: platformStorageApi.overview,
    tenants: () => platformStorageApi.tenants({ page: 1, page_size: 25 }),
  }), []);
  const state = useOperationalQuery(load);
  const blocking = <BlockingState state={state} label="o armazenamento" />;
  if (!state.data) return blocking;
  const { overview, tenants } = state.data.values;

  return <div className="space-y-5">
    <OperationalToolbar generatedAt={overview?.generated_at} stale={overview?.stale} status={overview?.status} loading={state.loading} onRefresh={() => void state.reload()} />
    <WarningBanner messages={state.data.errors} /><RefreshError error={state.error} />
    {overview && <><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Disco usado" value={formatPlatformBytes(overview.disk.used_bytes)} note={`${overview.disk.usage_percent.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% de ${formatPlatformBytes(overview.disk.total_bytes)}`} /><MetricCard label="Livre" value={formatPlatformBytes(overview.disk.free_bytes)} /><MetricCard label="Uploads" value={formatPlatformBytes(overview.uploads.bytes)} note={`${overview.uploads.files} arquivos`} /><MetricCard label="Otimizados" value={formatPlatformBytes(overview.optimized.bytes)} note={`${overview.optimized.files} arquivos`} /></div>
      <div className="grid gap-3 sm:grid-cols-2"><MetricCard label="Runtime do gateway" value={formatPlatformBytes(overview.baileys.bytes)} note={`${overview.baileys.files} arquivos`} /><MetricCard label="Legado sem atribuicao" value={formatPlatformBytes(overview.legacy_unattributed.bytes)} note={`${overview.legacy_unattributed.files} arquivos`} /></div></>}
    {tenants && <section className="space-y-3"><SectionTitle icon={<Archive size={18} />} title="Consumo por empresa" count={tenants.total} />{tenants.items.length ? <div className="grid gap-3 lg:grid-cols-2">{tenants.items.map((tenant) => <article key={tenant.tenant.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-black text-cream">{tenant.tenant.name}</h3><p className="mt-1 text-sm text-stone">{formatPlatformBytes(tenant.bytes)} · {tenant.files} arquivos</p></div><StatusBadge status={tenant.usage_state} /></div><p className="mt-3 text-xs text-stone">Limite: {formatPlatformBytes(tenant.limit_bytes)}{tenant.usage_percent == null ? "" : ` · ${tenant.usage_percent.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% utilizado`}</p></article>)}</div> : <EmptyState icon={<HardDrive size={30} />} title="Nenhum consumo atribuido" detail="A consulta nao retornou armazenamento atribuido a empresas." />}</section>}
  </div>;
}

type BackupParts = { overview: ApiPlatformBackupsOverview; runs: ApiPlatformBackupRuns };

export function PlatformBackups() {
  const load = useCallback(() => loadOperationalParts<BackupParts>({
    overview: platformBackupsApi.overview,
    runs: () => platformBackupsApi.runs(20),
  }), []);
  const state = useOperationalQuery(load);
  const blocking = <BlockingState state={state} label="os backups" />;
  if (!state.data) return blocking;
  const { overview, runs } = state.data.values;

  return <div className="space-y-5">
    <OperationalToolbar generatedAt={overview?.generated_at} stale={overview?.stale} status={overview?.status} loading={state.loading} onRefresh={() => void state.reload()} />
    <WarningBanner messages={state.data.errors} /><RefreshError error={state.error} />
    {overview && <><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Ultima tentativa" value={formatPlatformDate(overview.last_attempt_at)} /><MetricCard label="Ultimo sucesso" value={formatPlatformDate(overview.last_success_at)} /><MetricCard label="Idade do backup" value={formatPlatformDuration(overview.age_seconds)} /><MetricCard label="Teste de restauracao" value={<StatusBadge status={overview.restore_drill.status} />} note={`Ultimo teste: ${formatPlatformDate(overview.restore_drill.last_tested_at)}`} /></div>
      <section className="space-y-3"><SectionTitle icon={<DatabaseBackup size={18} />} title="Componentes do ultimo backup" count={overview.components.length} />{overview.components.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{overview.components.map((component) => <article key={component.key} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-center justify-between gap-3"><h3 className="font-black text-cream">{component.key}</h3><StatusBadge status={component.status} /></div><p className="mt-2 text-sm text-stone">{formatPlatformBytes(component.size_bytes)} · {component.validated ? "Validado" : "Sem validacao confirmada"}</p></article>)}</div> : <EmptyState icon={<DatabaseBackup size={30} />} title="Nenhum componente" detail="O snapshot de backup nao publicou componentes." />}</section></>}
    {runs && <section className="space-y-3"><SectionTitle icon={<Archive size={18} />} title="Execucoes recentes" count={runs.items.length} />{runs.items.length ? <div className="grid gap-3 lg:grid-cols-2">{runs.items.map((run) => <article key={run.run_id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="font-black text-cream">Execucao {run.run_id.slice(0, 12)}</h3><p className="mt-1 text-sm text-stone">Inicio: {formatPlatformDate(run.started_at)} · Fim: {formatPlatformDate(run.finished_at)}</p></div><StatusBadge status={run.status} /></div><p className="mt-3 text-xs text-stone">{run.components.length} componentes{run.failure_phase ? ` · Falha em ${run.failure_phase}` : ""}{run.failure_code ? ` (${run.failure_code})` : ""}</p></article>)}</div> : <EmptyState icon={<DatabaseBackup size={30} />} title="Nenhuma execucao" detail="O backend nao retornou historico de execucoes." />}</section>}
  </div>;
}
