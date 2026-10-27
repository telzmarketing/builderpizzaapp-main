import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Check,
  ChevronRight,
  CirclePause,
  CirclePlay,
  Clock3,
  Database,
  Loader2,
  RefreshCw,
  UserRound,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  kdsApi,
  type KdsMyQueue,
  type KdsPresenceState,
  type KdsProductionTask,
} from "@/lib/api";

const POLL_INTERVAL_MS = 10_000;
const PRESENCE_LABELS: Record<KdsPresenceState, string> = {
  offline: "Offline",
  available: "Disponível",
  in_production: "Em produção",
  paused: "Pausa",
};

function keyFor(scope: string, id: string) {
  const random =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`;
  return `kds:${scope}:${id}:${random}`;
}

function elapsedSeconds(value?: string | null) {
  if (!value) return 0;
  const time = Date.parse(value);
  return Number.isFinite(time)
    ? Math.max(0, Math.floor((Date.now() - time) / 1000))
    : 0;
}

export function formatTimer(task: KdsProductionTask) {
  const elapsed = elapsedSeconds(task.started_at);
  const total = Math.max(0, task.estimated_seconds ?? 0);
  const remaining = total ? Math.max(0, total - elapsed) : elapsed;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Não foi possível atualizar a fila KDS.";
}

export function consumptionLabel(task: KdsProductionTask) {
  if (task.consumption_mode === "attempts")
    return "Consumo desta tentativa confirmado";
  if (task.consumption_mode === "legacy_covered")
    return "Consumo coberto pelo regime legado";
  if (task.consumption_mode === "not_required")
    return "Sem consumo de estoque nesta unidade";
  return "Consumo aguardando confirmação do servidor";
}

export function StockCountdown({
  task,
  onConfirm,
}: {
  task: KdsProductionTask;
  onConfirm: () => Promise<void>;
}) {
  const [remaining, setRemaining] = useState(5);
  const confirm = useRef(onConfirm);
  confirm.current = onConfirm;
  useEffect(() => {
    // The deadline comes from the server; local clock changes cannot authorize stock.
    const delay = Math.max(
      0,
      Date.parse(task.stock_check_after || "") -
        Date.parse(task.server_time || ""),
    );
    if (!Number.isFinite(delay)) return;
    const deadline = performance.now() + delay;
    const update = () =>
      setRemaining(
        Math.max(0, Math.ceil((deadline - performance.now()) / 1000)),
      );
    update();
    const interval = window.setInterval(update, 250);
    const timeout = window.setTimeout(() => {
      void confirm.current();
    }, delay + 50);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [task.id, task.version, task.stock_check_after, task.server_time]);
  return (
    <div
      role="status"
      className="mt-3 rounded-lg border border-sky-400/40 bg-sky-500/10 p-3 font-bold text-sky-200"
    >
      {remaining
        ? `Conferindo estoque… ${remaining}s`
        : "Aguardando confirmação do servidor…"}
      <p className="mt-1 text-xs font-normal">
        Nenhuma baixa durante a contagem.
      </p>
    </div>
  );
}

export type TaskAction =
  | "start"
  | "confirm-stock"
  | "return-to-service"
  | "finish-assembly"
  | "start-oven"
  | "complete-oven"
  | "check";
const ACTION_LABELS: Record<TaskAction, string> = {
  start: "Conferência de estoque iniciada",
  "confirm-stock": "Estoque disponível — iniciando preparo",
  "return-to-service": "Pedido encaminhado ao atendimento",
  "finish-assembly": "Montagem concluída",
  "start-oven": "Assamento iniciado",
  "complete-oven": "Assamento concluído",
  check: "Unidade conferida",
};

export interface KdsWorkspaceProps {
  queue: KdsMyQueue | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  busy: string | null;
  selected: string[];
  targetOperator: string;
  setSelected: (ids: string[]) => void;
  setTargetOperator: (id: string) => void;
  load: (manual?: boolean) => Promise<void>;
  updatePresence: (state: KdsPresenceState) => Promise<void>;
  command: (task: KdsProductionTask, action: TaskAction) => Promise<void>;
  redistribute: () => Promise<void>;
}

export default function KdsMultiOperatorBoard({
  renderWorkspace,
}: {
  renderWorkspace?: (props: KdsWorkspaceProps) => ReactNode;
}) {
  const { toast } = useToast();
  const [queue, setQueue] = useState<KdsMyQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [targetOperator, setTargetOperator] = useState("");
  const [, setTick] = useState(0);

  const load = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      setQueue(await kdsApi.myQueue());
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [load]);

  useEffect(() => {
    const interval = window.setInterval(
      () => setTick((value) => value + 1),
      1_000,
    );
    return () => window.clearInterval(interval);
  }, []);

  const presence = queue?.presence;
  const operators = useMemo(
    () => queue?.available_operators ?? [],
    [queue?.available_operators],
  );

  useEffect(() => {
    if (!presence) return;
    const heartbeat = window.setInterval(() => {
      void kdsApi
        .heartbeat(
          {
            operational_session_id: `kds:${presence.operator_id}`,
            station_id: presence.station_id,
            expected_version: presence.version,
          },
          keyFor("heartbeat", presence.operator_id),
        )
        .catch(() => {
          // A transient heartbeat failure is surfaced by the next queue poll;
          // it must not change presence locally or retry a command implicitly.
        });
    }, 30_000);
    return () => window.clearInterval(heartbeat);
  }, [presence?.operator_id, presence?.version]);
  const updatePresence = async (state: KdsPresenceState) => {
    if (!presence) return;
    setBusy("presence");
    try {
      const updated = await kdsApi.setPresence(
        { state, expected_version: presence.version },
        keyFor("presence", state),
      );
      setQueue((current) =>
        current ? { ...current, presence: updated } : current,
      );
      toast({ title: `Presença: ${PRESENCE_LABELS[state]}` });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({
        title: "Presença não atualizada",
        description: message,
        variant: "destructive",
      });
    } finally {
      setBusy(null);
    }
  };

  const command = async (task: KdsProductionTask, action: TaskAction) => {
    setBusy(task.id);
    try {
      const updated = await kdsApi.commandTask(
        task.id,
        action,
        {
          expected_version: task.version,
          ...(action === "check" ? { approved: true } : {}),
        },
        keyFor(action, task.id),
      );
      setQueue((current) =>
        current
          ? {
              ...current,
              tasks: current.tasks.map((item) =>
                item.id === task.id ? updated : item,
              ),
            }
          : current,
      );
      toast({
        title:
          updated.state === "aguardando_analise"
            ? "Estoque indisponível — aguardando análise"
            : ACTION_LABELS[action],
        variant:
          updated.state === "aguardando_analise" ? "destructive" : "default",
      });
      void load();
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({
        title: "Comando não concluído",
        description: message,
        variant: "destructive",
      });
      void load(true);
    } finally {
      setBusy(null);
    }
  };

  const redistribute = async () => {
    if (!targetOperator || selected.length === 0) return;
    const selectedTasks = (queue?.tasks ?? []).filter((task) =>
      selected.includes(task.id),
    );
    setBusy("redistribute");
    try {
      const result = await kdsApi.redistribute(
        {
          task_ids: selected,
          to_operator_id: targetOperator,
          from_operator_id: presence?.operator_id ?? null,
          reason: "Redistribuição operacional pelo painel KDS",
          expected_versions: Object.fromEntries(
            selectedTasks.map((task) => [task.id, task.version]),
          ),
        },
        keyFor("redistribute", selected.join(",")),
      );
      setQueue(result);
      setSelected([]);
      toast({ title: "Fila redistribuída" });
    } catch (caught) {
      const message = errorMessage(caught);
      setError(message);
      toast({
        title: "Redistribuição não concluída",
        description: message,
        variant: "destructive",
      });
      void load(true);
    } finally {
      setBusy(null);
    }
  };

  if (renderWorkspace)
    return (
      <>
        {renderWorkspace({
          queue,
          loading,
          refreshing,
          error,
          busy,
          selected,
          targetOperator,
          setSelected,
          setTargetOperator,
          load,
          updatePresence,
          command,
          redistribute,
        })}
      </>
    );

  if (loading && !queue)
    return (
      <div className="flex items-center gap-2 rounded-2xl border border-surface-03 bg-surface-02 p-5 text-stone">
        <Loader2 className="animate-spin text-gold" /> Carregando fila
        multioperador...
      </div>
    );

  return (
    <>
      <style>{`
        @media (min-width: 1024px) {
          section[aria-label="KDS multioperador"] {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 17rem;
            align-items: stretch;
          }
          section[aria-label="KDS multioperador"] > header,
          section[aria-label="KDS multioperador"] > [role="alert"],
          section[aria-label="KDS multioperador"] > div:not(.grid) {
            grid-column: 1 / -1;
          }
          section[aria-label="KDS multioperador"] > .grid.gap-3.sm\\:grid-cols-3 {
            grid-column: 2;
            grid-row: 3;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
          }
          section[aria-label="KDS multioperador"] > .grid.gap-3.sm\\:grid-cols-3 > div {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 0.75rem;
          }
          section[aria-label="KDS multioperador"] > .grid.gap-3.sm\\:grid-cols-3 + .rounded-xl {
            grid-column: 1;
            grid-row: 3;
            min-height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          section[aria-label="KDS multioperador"]:has(> [role="alert"]) > .grid.gap-3.sm\\:grid-cols-3,
          section[aria-label="KDS multioperador"]:has(> [role="alert"]) > .grid.gap-3.sm\\:grid-cols-3 + .rounded-xl {
            grid-row: 4;
          }
        }
      `}</style>
      <section
        className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-4 shadow-soft"
        aria-label="KDS multioperador"
      >
        <header className="flex flex-col gap-3 border-b border-surface-03 pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-gold/10 text-gold">
              <Users />
            </span>
            <div>
              <h2 className="text-lg font-black">Fila multioperador</h2>
              <p className="text-sm text-stone">
                Atribuição, presença e tempo derivados do servidor
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {presence && (
              <span className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm font-bold">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${presence.state === "offline" ? "bg-stone" : presence.state === "paused" ? "bg-amber-300" : "bg-emerald-300"}`}
                />
                {PRESENCE_LABELS[presence.state]}
              </span>
            )}
            <button
              type="button"
              onClick={() =>
                void updatePresence(
                  presence?.state === "available" ? "paused" : "available",
                )
              }
              disabled={!presence || busy === "presence"}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 font-bold disabled:opacity-50"
            >
              {busy === "presence" ? (
                <Loader2 className="animate-spin" size={16} />
              ) : presence?.state === "available" ? (
                <CirclePause size={16} />
              ) : (
                <CirclePlay size={16} />
              )}
              {presence?.state === "available" ? "Pausar" : "Ficar disponível"}
            </button>
            <button
              type="button"
              aria-label="Atualizar fila multioperador"
              onClick={() => void load(true)}
              disabled={refreshing}
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 font-bold disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={refreshing ? "animate-spin" : ""}
              />{" "}
              Atualizar
            </button>
          </div>
        </header>

        {error && (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200"
          >
            <span className="flex items-center gap-2">
              <WifiOff size={16} />
              {error}
            </span>
            <button
              type="button"
              onClick={() => void load(true)}
              className="rounded-lg bg-red-500 px-3 py-2 font-bold text-white"
            >
              Tentar novamente
            </button>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-surface-03 bg-surface-01 p-3">
            <p className="text-xs font-bold uppercase text-stone">Minha fila</p>
            <strong className="text-2xl">{presence?.queue_count ?? 0}</strong>
          </div>
          <div className="rounded-xl border border-surface-03 bg-surface-01 p-3">
            <p className="text-xs font-bold uppercase text-stone">
              Operadores ativos
            </p>
            <strong className="text-2xl">
              {
                operators.filter((operator) => operator.state !== "offline")
                  .length
              }
            </strong>
          </div>
          <div className="rounded-xl border border-surface-03 bg-surface-01 p-3">
            <p className="text-xs font-bold uppercase text-stone">Sessão</p>
            <strong className="flex items-center gap-2 text-sm text-emerald-300">
              <Wifi size={16} /> Heartbeat ativo
            </strong>
          </div>
        </div>

        {(queue?.tasks ?? []).length === 0 ? (
          <div className="rounded-xl border border-dashed border-surface-03 p-8 text-center text-stone">
            Nenhuma tarefa atribuída a esta estação.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(queue?.tasks ?? []).map((task) => {
              const isSelected = selected.includes(task.id);
              const isBusy = busy === task.id;
              return (
                <article
                  key={task.id}
                  className={`rounded-xl border bg-surface-01 p-4 ${isSelected ? "border-gold" : "border-surface-03"}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(event) =>
                          setSelected((current) =>
                            event.target.checked
                              ? [...current, task.id]
                              : current.filter((id) => id !== task.id),
                          )
                        }
                        aria-label={`Selecionar tarefa ${task.order_code || task.id}`}
                        className="h-5 w-5 accent-gold"
                      />
                      <strong className="text-lg">
                        #
                        {(
                          task.order_code || task.order_id.slice(0, 8)
                        ).toUpperCase()}
                      </strong>
                    </label>
                    <span className="flex items-center gap-1 rounded-lg bg-surface-02 px-2 py-1 text-sm font-bold text-amber-300">
                      <Clock3 size={14} />
                      {formatTimer(task)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-stone">
                    {task.product_name || "Unidade de produção"} · unidade{" "}
                    {task.unit_index}
                  </p>
                  <p className="mt-1 text-xs uppercase tracking-wide text-stone">
                    {task.state} · prioridade {task.priority}
                  </p>
                  {task.state === "checking_stock" && (
                    <StockCountdown
                      task={task}
                      onConfirm={() => command(task, "confirm-stock")}
                    />
                  )}
                  {(task.state === "aguardando_analise" ||
                    task.state === "atendimento") && (
                    <div
                      role="alert"
                      className="mt-3 rounded-lg border border-red-400/50 bg-red-500/10 p-3 text-sm font-bold text-red-200"
                    >
                      {task.state === "atendimento"
                        ? "Encaminhado ao atendimento"
                        : "Aguardando análise do atendimento/gerência"}
                      <p className="mt-1 font-normal">
                        {task.blocked_reason ||
                          "Estoque não confirmado. Preparo bloqueado."}
                      </p>
                    </div>
                  )}
                  <div className="mt-3 rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-xs text-stone">
                    <p className="flex items-center gap-2 font-bold text-cream">
                      <Database size={14} className="text-gold" />{" "}
                      {consumptionLabel(task)}
                    </p>
                    {task.consumption_operation_id && (
                      <p
                        className="mt-1 truncate"
                        title={task.consumption_operation_id}
                      >
                        Operação: {task.consumption_operation_id}
                      </p>
                    )}
                    {task.composition_revision_id && (
                      <p
                        className="mt-1 truncate"
                        title={task.composition_revision_id}
                      >
                        Composição congelada: {task.composition_revision_id}
                      </p>
                    )}
                  </div>
                  <div className="mt-4 flex gap-2">
                    {(() => {
                      const action: TaskAction | null =
                        task.state === "queued" || task.state === "unassigned"
                          ? "start"
                          : task.state === "assembling"
                            ? "finish-assembly"
                            : task.state === "assembled"
                              ? task.requires_oven
                                ? "start-oven"
                                : "check"
                              : task.state === "baking"
                                ? "complete-oven"
                                : task.state === "checking"
                                  ? "check"
                                  : task.state === "aguardando_analise"
                                    ? "return-to-service"
                                    : null;
                      const label =
                        action === "start"
                          ? "Iniciar / OK"
                          : action === "finish-assembly"
                            ? "Concluir montagem"
                            : action === "start-oven"
                              ? "Iniciar forno"
                              : action === "complete-oven"
                                ? "Retirar do forno"
                                : action === "check"
                                  ? "Conferido — OK"
                                  : "Voltar para Atendimento";
                      return action ? (
                        <button
                          type="button"
                          onClick={() => void command(task, action)}
                          disabled={Boolean(busy)}
                          className={`flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg px-3 font-black text-white disabled:opacity-50 ${action === "return-to-service" ? "bg-red-600" : action === "start" ? "bg-orange-500" : "bg-emerald-600"}`}
                        >
                          {isBusy ? (
                            <Loader2 className="animate-spin" size={16} />
                          ) : (
                            <Check size={16} />
                          )}
                          {label}
                        </button>
                      ) : (
                        <span className="flex min-h-11 flex-1 items-center justify-center rounded-lg bg-surface-02 px-3 text-sm font-bold text-stone">
                          {task.state === "checking_stock"
                            ? "Conferência em andamento"
                            : "Aguardando atendimento"}
                        </span>
                      );
                    })()}
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {selected.length > 0 && (
          <div className="flex flex-col gap-3 rounded-xl border border-gold/40 bg-gold/5 p-3 sm:flex-row sm:items-center">
            <span className="text-sm font-bold">
              {selected.length} tarefa(s) selecionada(s)
            </span>
            <select
              value={targetOperator}
              onChange={(event) => setTargetOperator(event.target.value)}
              className="min-h-11 flex-1 rounded-lg border border-surface-03 bg-surface-01 px-3 text-sm"
              aria-label="Operador de destino"
            >
              <option value="">Escolha o operador de destino</option>
              {operators
                .filter(
                  (operator) =>
                    operator.operator_id !== presence?.operator_id &&
                    operator.state !== "offline",
                )
                .map((operator) => (
                  <option
                    key={operator.operator_id}
                    value={operator.operator_id}
                  >
                    {operator.operator_name} · {PRESENCE_LABELS[operator.state]}
                  </option>
                ))}
            </select>
            <button
              type="button"
              onClick={() => void redistribute()}
              disabled={!targetOperator || busy === "redistribute"}
              className="min-h-11 rounded-lg bg-gold px-4 font-black text-surface-00 disabled:opacity-50"
            >
              {busy === "redistribute" ? (
                <Loader2 className="animate-spin" size={16} />
              ) : (
                <UserRound size={16} />
              )}{" "}
              Redistribuir
            </button>
          </div>
        )}
      </section>
    </>
  );
}
