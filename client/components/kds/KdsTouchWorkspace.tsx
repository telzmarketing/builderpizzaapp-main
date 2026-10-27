import { useState } from "react";
import {
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  CirclePause,
  CirclePlay,
  ClipboardList,
  Flame,
  Hourglass,
  Loader2,
  Pizza,
  RefreshCw,
  StickyNote,
  UtensilsCrossed,
  Users,
  WifiOff,
} from "lucide-react";
import type {
  KdsKitchenOrder,
  KdsOrderItem,
  KdsProductionTask,
} from "@/lib/api";
import {
  consumptionLabel,
  formatTimer,
  StockCountdown,
  type KdsWorkspaceProps,
  type TaskAction,
} from "./KdsMultiOperatorBoard";
import KdsRecipeDetails from "./KdsRecipeDetails";

const panel =
  "min-w-0 overflow-hidden rounded-2xl border border-[#263f53] bg-[#091521]";
const control =
  "inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[#30485d] bg-[#0b1926] px-4 font-bold text-slate-100 disabled:opacity-40 active:scale-[0.98]";
const stateLabels: Record<string, string> = {
  queued: "Aguardando",
  unassigned: "Não iniciada",
  checking_stock: "Conferindo estoque",
  assembling: "Em montagem",
  assembled: "Montada",
  baking: "No forno",
  checking: "Em conferência",
  ready: "Pronta",
  blocked: "Bloqueada",
  aguardando_analise: "Aguardando análise",
  atendimento: "No atendimento",
  cancelled: "Cancelada",
};
const presenceLabels: Record<string, string> = {
  offline: "Offline",
  available: "Disponível",
  in_production: "Em produção",
  paused: "Em pausa",
};
const code = (order: { order_code?: string | null; id: string }) =>
  (order.order_code || order.id.slice(0, 8)).toUpperCase();
const channel = (order: KdsKitchenOrder) =>
  order.sales_channel === "dine_in" || order.fulfillment_type === "dine_in"
    ? "Salão"
    : order.fulfillment_type === "pickup"
      ? "Balcão"
      : "Delivery";
const description = (item: KdsOrderItem) =>
  [
    item.flavors?.length
      ? item.flavors.map((flavor) => flavor.name).join(" / ")
      : item.product_name,
    item.selected_size,
    item.selected_crust_type,
    item.selected_drink_variant,
  ]
    .filter(Boolean)
    .join(" · ");
const time = (value: string) =>
  new Date(value).toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
const elapsed = (value: string) => {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - Date.parse(value)) / 60_000),
  );
  return minutes < 60
    ? `${minutes} min`
    : `${Math.floor(minutes / 60)}h ${minutes % 60}min`;
};

function ProductVisual({
  item,
  small = false,
}: {
  item?: KdsOrderItem;
  small?: boolean;
}) {
  const image = item?.recipe?.methods?.find(
    (method) => method.reference_image_url,
  )?.reference_image_url;
  const [failed, setFailed] = useState<string | null>(null);
  return (
    <div
      className={`flex shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-[#25394a] bg-[#0d1d2a] text-amber-400 ${small ? "h-14 w-14" : "aspect-square w-full max-w-64 xl:max-w-[200px]"}`}
    >
      {image && failed !== image ? (
        <img
          src={image}
          alt={`Referência de preparo: ${item?.product_name || "item"}`}
          onError={() => setFailed(image)}
          className="h-full w-full object-cover"
        />
      ) : (
        <Pizza size={small ? 32 : 110} strokeWidth={1.3} aria-hidden="true" />
      )}
    </div>
  );
}

function taskAction(
  task?: KdsProductionTask,
): { action: TaskAction; label: string } | null {
  if (!task) return null;
  switch (task.state) {
    case "queued":
    case "unassigned":
      return { action: "start", label: "Iniciar / OK" };
    case "assembling":
      return { action: "finish-assembly", label: "Concluir montagem" };
    case "assembled":
      return task.requires_oven
        ? { action: "start-oven", label: "Iniciar forno" }
        : { action: "check", label: "Conferido — OK" };
    case "baking":
      return { action: "complete-oven", label: "Retirar do forno" };
    case "checking":
      return { action: "check", label: "Conferido — OK" };
    case "aguardando_analise":
      return { action: "return-to-service", label: "Voltar para Atendimento" };
    default:
      return null;
  }
}

interface Props extends KdsWorkspaceProps {
  orders: KdsKitchenOrder[];
  ordersLoading: boolean;
  updating: string | null;
  startOrder: (order: KdsKitchenOrder) => Promise<void>;
  finishOrder: (order: KdsKitchenOrder) => Promise<void>;
}

export default function KdsTouchWorkspace(props: Props) {
  const { queue, orders, busy, selected, targetOperator } = props;
  const [orderId, setOrderId] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const tasks = queue?.tasks ?? [];
  const activeTask =
    tasks.find((task) => task.id === queue?.presence?.active_task_id) ??
    tasks.find((task) =>
      [
        "assembling",
        "assembled",
        "baking",
        "checking",
        "checking_stock",
      ].includes(task.state),
    ) ??
    tasks[0];
  const selectedTask = tasks.find((candidate) => candidate.id === taskId);
  const order =
    selectedTask &&
    !orders.some((candidate) => candidate.id === selectedTask.order_id)
      ? undefined
      : (orders.find((candidate) => candidate.id === selectedTask?.order_id) ??
        orders.find((candidate) => candidate.id === orderId) ??
        orders.find((candidate) => candidate.id === activeTask?.order_id) ??
        orders.find((candidate) => candidate.status === "preparing") ??
        orders[0]);
  const orderTasks = tasks.filter((task) => task.order_id === order?.id);
  const focusTasks = order ? orderTasks : tasks;
  const task =
    focusTasks.find((candidate) => candidate.id === taskId) ??
    focusTasks.find((candidate) => candidate.id === activeTask?.id) ??
    focusTasks[0];
  const item =
    order?.items.find((candidate) => candidate.id === task?.order_item_id) ??
    order?.items[0];
  const units = order?.production_units ?? [];
  const readyCount = units.filter((unit) => unit.state === "ready").length;
  const allReady = units.length > 0 && readyCount === units.length;
  const action = taskAction(task);
  const taskIndex = task
    ? focusTasks.findIndex((candidate) => candidate.id === task.id)
    : -1;
  const presence = queue?.presence;
  const operators = queue?.available_operators ?? [];
  const chooseOrder = (id: string) => {
    setOrderId(id);
    setTaskId(null);
  };
  const phase =
    task?.state === "ready"
      ? 3
      : task?.state === "checking"
        ? 2
        : task?.state === "baking"
          ? 1
          : ["assembling", "assembled"].includes(task?.state ?? "")
            ? 0
            : -1;
  const ingredients = item?.recipe?.ingredients ?? [];

  return (
    <div className="space-y-3 p-3 sm:p-4">
      {props.error && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-red-200"
        >
          <span className="flex items-center gap-2">
            <WifiOff size={20} />
            {props.error}
          </span>
          <button className={control} onClick={() => void props.load(true)}>
            Tentar novamente
          </button>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-300">
        <p className="flex items-center gap-2">
          <Users size={18} className="text-amber-400" />
          {presence
            ? [
                presence.operator_name,
                presence.station_id && `Estação: ${presence.station_id}`,
                presenceLabels[presence.state],
              ]
                .filter(Boolean)
                .join(" · ")
            : "Conectando estação"}
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={control}
            onClick={() =>
              void props.updatePresence(
                presence?.state === "available" ? "paused" : "available",
              )
            }
            disabled={!presence || Boolean(busy)}
          >
            {presence?.state === "available" ? (
              <CirclePause size={18} />
            ) : (
              <CirclePlay size={18} />
            )}
            {busy === "presence"
              ? "Atualizando..."
              : presence?.state === "available"
                ? "Pausar presença"
                : "Ficar disponível"}
          </button>
          <button
            type="button"
            aria-label="Atualizar fila multioperador"
            className={control}
            disabled={props.refreshing}
            onClick={() => void props.load(true)}
          >
            <RefreshCw
              size={18}
              className={props.refreshing ? "animate-spin" : ""}
            />
            Fila
          </button>
        </div>
      </div>
      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(210px,0.95fr)_minmax(0,2fr)_minmax(220px,0.95fr)] xl:items-start">
        <section className={panel} aria-label="Fila de pedidos">
          <header className="flex items-center gap-3 border-b border-[#263f53] p-4">
            <Hourglass className="shrink-0 text-amber-400" size={30} />
            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-bold">Fila de pedidos</h2>
              <p className="mt-1 text-xs text-slate-400">
                Selecione para acompanhar o preparo
              </p>
            </div>
            <span className="rounded-full bg-[#1c3347] px-3 py-1 font-bold">
              {orders.length}
            </span>
          </header>
          <div className="space-y-3 p-3 xl:max-h-[calc(100vh-290px)] xl:overflow-y-auto">
            {props.ordersLoading ? (
              <p
                role="status"
                className="flex items-center gap-2 p-4 text-slate-400"
              >
                <Loader2 className="animate-spin" />
                Carregando pedidos...
              </p>
            ) : (
              orders.length === 0 && (
                <p className="p-6 text-center text-slate-400">
                  Nenhum pedido na cozinha.
                </p>
              )
            )}
            {orders.map((candidate) => (
              <button
                key={candidate.id}
                type="button"
                onClick={() => chooseOrder(candidate.id)}
                aria-pressed={order?.id === candidate.id}
                className={`relative w-full overflow-hidden rounded-xl border p-4 text-left transition-colors ${order?.id === candidate.id ? "border-amber-400 bg-amber-400/5" : "border-[#263f53] bg-[#07111c] hover:bg-[#102335]"}`}
              >
                <span
                  className={`absolute inset-y-0 left-0 w-1.5 ${candidate.status === "preparing" ? "bg-amber-400" : "bg-cyan-400"}`}
                />
                <span className="flex flex-wrap justify-between gap-2">
                  <strong className="text-xl">#{code(candidate)}</strong>
                  <span className="text-right text-slate-300">
                    <span className="block">{time(candidate.created_at)}</span>
                    <span className="block text-xs text-slate-400">
                      há {elapsed(candidate.created_at)}
                    </span>
                  </span>
                </span>
                <span className="my-3 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-lg bg-[#1c3347] px-3 py-1 font-bold">
                    {channel(candidate)}
                  </span>
                  <span className="rounded-lg bg-[#172a3c] px-3 py-1">
                    {candidate.status === "ready_for_pickup"
                      ? "Pronto para servir"
                      : candidate.status === "preparing"
                        ? "Em preparo"
                        : "Aguardando início"}
                  </span>
                </span>
                <span className="block space-y-1 text-sm">
                  {candidate.items.map((line) => (
                    <span key={line.id} className="block break-words">
                      {line.quantity} × {description(line)}
                    </span>
                  ))}
                </span>
              </button>
            ))}
            {tasks
              .filter(
                (candidate) =>
                  !orders.some((entry) => entry.id === candidate.order_id),
              )
              .map((candidate) => (
                <button
                  type="button"
                  key={candidate.id}
                  className={`${control} w-full break-words text-left`}
                  onClick={() => {
                    setOrderId(null);
                    setTaskId(candidate.id);
                  }}
                >
                  #{candidate.order_code || candidate.order_id.slice(0, 8)} ·{" "}
                  {candidate.product_name}
                </button>
              ))}
          </div>
        </section>
        <section
          className={`${panel} border-amber-400 shadow-[0_0_24px_rgba(251,191,36,0.04)]`}
          aria-label="Pedido em preparo"
        >
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#263f53] bg-[#101a22] p-4">
            <div>
              <p className="text-xl font-bold text-amber-400">
                {order?.status === "ready_for_pickup"
                  ? "Pronto para servir"
                  : order?.status === "preparing" || task
                    ? "Pedido em preparo"
                    : "Aguardando preparo"}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <h2 className="text-3xl font-black">
                  {order
                    ? `#${code(order)}`
                    : task
                      ? `#${task.order_code || task.order_id.slice(0, 8)}`
                      : "Sua estação"}
                </h2>
                {order && (
                  <span className="rounded-xl bg-[#233448] px-3 py-1 text-sm font-bold">
                    {channel(order)}
                  </span>
                )}
              </div>
            </div>
            {order && (
              <div className="text-right">
                <p className="text-xl">{time(order.created_at)}</p>
                <p className="text-xs text-slate-400">Horário de entrada</p>
              </div>
            )}
          </header>
          <div className="space-y-4 p-4">
            {props.loading && !queue ? (
              <p className="flex min-h-64 items-center justify-center gap-2 text-slate-400">
                <Loader2 className="animate-spin" />
                Carregando fila multioperador...
              </p>
            ) : !order && !task ? (
              <div className="flex min-h-72 flex-col items-center justify-center gap-4 text-slate-400">
                <UtensilsCrossed size={48} />
                <p>Nenhuma tarefa atribuída a esta estação.</p>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-2xl font-bold">
                    {task ? `Unidade ${task.unit_index}` : "Itens do pedido"}
                  </h3>
                  {focusTasks.length > 0 && (
                    <nav
                      className="flex items-center gap-3"
                      aria-label="Navegação das unidades"
                    >
                      <button
                        type="button"
                        aria-label="Unidade anterior"
                        className={`${control} px-3`}
                        disabled={taskIndex <= 0}
                        onClick={() =>
                          setTaskId(focusTasks[taskIndex - 1]?.id ?? null)
                        }
                      >
                        <ChevronLeft />
                      </button>
                      <span>
                        {taskIndex + 1} / {focusTasks.length}
                      </span>
                      <button
                        type="button"
                        aria-label="Próxima unidade"
                        className={`${control} border-amber-400 bg-amber-400 px-3 !text-slate-950`}
                        disabled={taskIndex >= focusTasks.length - 1}
                        onClick={() =>
                          setTaskId(focusTasks[taskIndex + 1]?.id ?? null)
                        }
                      >
                        <ChevronRight />
                      </button>
                    </nav>
                  )}
                </div>
                <div className="grid items-center gap-4 sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)]">
                  <ProductVisual item={item} />
                  <div className="min-w-0">
                    <h3 className="break-words text-3xl font-bold">
                      {item
                        ? description(item)
                        : task?.product_name || "Unidade de produção"}
                    </h3>
                    {ingredients.length > 0 ? (
                      <ul className="mt-3 space-y-2">
                        {ingredients.map((ingredient, index) => (
                          <li
                            key={`${ingredient.inventory_item_id}-${index}`}
                            className="flex flex-wrap justify-between gap-x-3 text-base text-slate-200"
                          >
                            <span className="min-w-0 break-words">
                              {ingredient.name}
                            </span>
                            <strong className="text-amber-300">
                              {ingredient.quantity}{" "}
                              {ingredient.unit_symbol ||
                                ingredient.unit_id ||
                                ""}
                            </strong>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-4 text-sm text-slate-400">
                        Consulte os ingredientes e o método na ficha técnica.
                      </p>
                    )}
                    {item?.add_ons?.length > 0 && (
                      <p className="mt-4 break-words text-sm text-amber-200">
                        Adicionais: {item.add_ons.join(", ")}
                      </p>
                    )}
                  </div>
                </div>
                {task ? (
                  <section
                    className="space-y-3 border-t border-[#263f53] pt-4"
                    aria-label="Etapas de produção"
                  >
                    <div className="flex flex-wrap items-end justify-between gap-3">
                      <div>
                        <p className="font-bold text-amber-300">
                          {stateLabels[task.state] ?? task.state}
                        </p>
                        <p className="mt-1 text-xs text-slate-400">
                          {consumptionLabel(task)}
                        </p>
                      </div>
                      {task.started_at && (
                        <div className="text-right">
                          <p className="text-4xl font-bold tabular-nums">
                            {formatTimer(task)}
                          </p>
                          <p className="text-xs text-slate-400">
                            {task.estimated_seconds
                              ? "Tempo restante estimado"
                              : "Tempo decorrido"}
                          </p>
                        </div>
                      )}
                    </div>
                    <div
                      className="h-2 overflow-hidden rounded-full bg-[#1c3347]"
                      role="progressbar"
                      aria-label="Etapas da unidade"
                      aria-valuemin={0}
                      aria-valuemax={3}
                      aria-valuenow={Math.max(0, phase)}
                    >
                      <div
                        className="h-full rounded-full bg-emerald-400 transition-all"
                        style={{ width: `${(Math.max(0, phase) / 3) * 100}%` }}
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        "Montagem",
                        task.requires_oven ? "No forno" : "Sem forno",
                        "Finalização",
                      ].map((label, index) => (
                        <div
                          key={label}
                          className={`flex flex-col items-center gap-2 text-center text-sm ${phase === index ? "text-amber-400" : phase > index ? "text-emerald-400" : "text-slate-500"}`}
                        >
                          <span
                            className={`flex h-10 w-10 items-center justify-center rounded-full border-2 ${phase === index ? "border-amber-400" : "border-current"}`}
                          >
                            {phase > index ? (
                              <Check size={20} />
                            ) : index === 1 ? (
                              <Flame size={20} />
                            ) : index === 0 ? (
                              <Pizza size={20} />
                            ) : (
                              <Check size={20} />
                            )}
                          </span>
                          {label}
                        </div>
                      ))}
                    </div>
                    {task.state === "checking_stock" && (
                      <StockCountdown
                        task={task}
                        onConfirm={() => props.command(task, "confirm-stock")}
                      />
                    )}
                    {["aguardando_analise", "atendimento", "blocked"].includes(
                      task.state,
                    ) && (
                      <p
                        role="alert"
                        className="rounded-xl border border-red-400/40 bg-red-400/10 p-4 text-red-200"
                      >
                        {task.blocked_reason ||
                          "Estoque não confirmado. Preparo bloqueado."}
                      </p>
                    )}
                    {(task.consumption_operation_id ||
                      task.composition_revision_id) && (
                      <details className="text-xs text-slate-400">
                        <summary className="cursor-pointer py-2">
                          Detalhes de rastreabilidade
                        </summary>
                        <p className="break-all">
                          Operação: {task.consumption_operation_id || "—"}
                        </p>
                        <p className="break-all">
                          Composição congelada:{" "}
                          {task.composition_revision_id || "—"}
                        </p>
                      </details>
                    )}
                  </section>
                ) : (
                  <p className="rounded-xl border border-[#263f53] p-4 text-sm text-slate-400">
                    {order?.status === "ready_for_pickup"
                      ? "Preparo concluído. Pedido disponível para servir no salão."
                      : order?.status === "preparing"
                        ? "Nenhuma tarefa deste pedido atribuída a esta estação. Acompanhe as unidades no resumo."
                        : "Inicie o preparo para encaminhar as unidades à fila do pizzaiolo."}
                  </p>
                )}
                <details className="rounded-xl border border-[#263f53] bg-[#07111c] p-2">
                  <summary className="flex min-h-12 cursor-pointer items-center gap-3 font-bold">
                    <BookOpen size={24} />
                    Ingredientes e método
                  </summary>
                  <div className="mt-4 space-y-4">
                    {order?.items.map((line) => (
                      <section key={line.id}>
                        <h4 className="mb-2 font-bold">
                          {line.quantity} × {description(line)}
                        </h4>
                        <KdsRecipeDetails recipe={line.recipe} />
                      </section>
                    )) ?? (
                      <p className="text-sm text-slate-400">
                        Ficha técnica indisponível para esta unidade.
                      </p>
                    )}
                  </div>
                </details>
                {action && task && (
                  <button
                    type="button"
                    disabled={Boolean(busy)}
                    onClick={() => void props.command(task, action.action)}
                    className={`flex min-h-14 w-full items-center justify-center gap-3 rounded-xl px-5 text-lg font-black text-slate-950 disabled:opacity-40 ${action.action === "return-to-service" ? "bg-red-400" : "bg-amber-400 hover:bg-amber-300"}`}
                  >
                    {busy === task.id ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Check size={28} />
                    )}
                    {busy === task.id ? "Processando..." : action.label}
                  </button>
                )}
                {order &&
                  (order.status === "paid" || order.status === "pago") && (
                    <button
                      type="button"
                      disabled={Boolean(props.updating)}
                      onClick={() => void props.startOrder(order)}
                      className="flex min-h-14 w-full items-center justify-center gap-3 rounded-xl bg-amber-400 p-4 text-lg font-black text-slate-950 disabled:opacity-40"
                    >
                      {props.updating === order.id ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <CirclePlay />
                      )}
                      Iniciar preparo do pedido
                    </button>
                  )}
                {order?.status === "preparing" && (
                  <button
                    type="button"
                    disabled={!allReady || Boolean(props.updating)}
                    onClick={() => void props.finishOrder(order)}
                    className="flex min-h-12 w-full items-center justify-center gap-3 rounded-xl bg-emerald-400 p-3 text-base font-black text-slate-950 disabled:opacity-40"
                  >
                    {props.updating === order.id ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Check />
                    )}
                    {props.updating === order.id
                      ? "Finalizando preparo..."
                      : allReady
                        ? "Finalizar preparo do pedido"
                        : "Aguardando todas as unidades"}
                  </button>
                )}
              </>
            )}
          </div>
        </section>
        <aside className="min-w-0 space-y-3">
          <section className={panel}>
            <header className="flex items-center gap-3 border-b border-[#263f53] p-4">
              <ClipboardList size={30} className="shrink-0 text-slate-300" />
              <h2 className="text-lg font-bold">
                Resumo do pedido
                {order && (
                  <span className="block text-base">#{code(order)}</span>
                )}
              </h2>
            </header>
            <div className="space-y-3 p-3">
              {order ? (
                <>
                  <div className="grid grid-cols-2 gap-3 rounded-xl bg-[#07111c] p-3 text-sm">
                    <div>
                      <p className="mb-1 text-slate-400">Canal</p>
                      <strong>{channel(order)}</strong>
                    </div>
                    <div>
                      <p className="mb-1 text-slate-400">Unidades prontas</p>
                      <strong>
                        {readyCount} / {units.length}
                      </strong>
                    </div>
                  </div>
                  {order.delivery?.delivery_person_name && (
                    <p className="text-sm text-emerald-300">
                      Motoboy: {order.delivery.delivery_person_name}
                    </p>
                  )}
                  {units.length ? (
                    units.map((unit) => {
                      const unitTask = tasks.find(
                        (entry) => entry.id === unit.task_id,
                      );
                      const line = order.items.find(
                        (entry) => entry.id === unit.order_item_id,
                      );
                      return (
                        <button
                          key={unit.id}
                          type="button"
                          disabled={!unitTask}
                          onClick={() => setTaskId(unitTask?.id ?? null)}
                          className={`flex min-h-20 w-full items-center gap-3 rounded-xl border p-3 text-left disabled:cursor-default ${unitTask?.id === task?.id ? "border-amber-400 bg-amber-400/5" : "border-[#263f53] bg-[#07111c]"}`}
                        >
                          <ProductVisual item={line} small />
                          <span className="min-w-0 flex-1">
                            <strong className="block break-words text-sm">
                              {unit.unit_index}.{" "}
                              {line
                                ? description(line)
                                : unit.product_name || "Unidade"}
                            </strong>
                            <span
                              className={`mt-1 block text-xs ${unit.state === "ready" ? "text-emerald-300" : "text-slate-400"}`}
                            >
                              {stateLabels[unitTask?.state ?? unit.state] ??
                                unit.state}
                            </span>
                          </span>
                        </button>
                      );
                    })
                  ) : (
                    <p className="p-3 text-sm text-slate-400">
                      As unidades de produção ainda não foram carregadas. O
                      pedido não pode ser finalizado.
                    </p>
                  )}
                </>
              ) : (
                <p className="p-4 text-sm text-slate-400">
                  Selecione um pedido da fila.
                </p>
              )}
            </div>
          </section>
          <section className={panel}>
            <h2 className="flex items-center gap-3 border-b border-[#263f53] p-4 text-lg font-bold">
              <StickyNote className="shrink-0" />
              Observações do pedido
            </h2>
            <div className="space-y-3 p-4 text-sm">
              {order?.notes && (
                <p className="whitespace-pre-wrap break-words rounded-xl bg-amber-400/10 p-3 text-amber-200">
                  {order.notes}
                </p>
              )}
              {order?.items
                .filter((line) => line.notes)
                .map((line) => (
                  <p
                    key={line.id}
                    className="whitespace-pre-wrap break-words rounded-xl bg-amber-400/10 p-3 text-amber-200"
                  >
                    <strong className="mb-1 block">{line.product_name}</strong>
                    {line.notes}
                  </p>
                ))}
              {!order?.notes && !order?.items.some((line) => line.notes) && (
                <p className="py-5 text-slate-400">Sem observações.</p>
              )}
            </div>
          </section>
          <section className={panel}>
            <h2 className="p-4 text-sm font-bold text-slate-300">
              Equipe e redistribuição
            </h2>
            <div className="space-y-3 px-4 pb-4 text-sm">
              <p className="text-slate-400">
                {presence?.queue_count ?? 0} na minha fila ·{" "}
                {
                  operators.filter((operator) => operator.state !== "offline")
                    .length
                }{" "}
                operadores ativos
              </p>
              {tasks.length > 0 && (
                <details>
                  <summary className="min-h-12 cursor-pointer py-3 font-bold">
                    Selecionar tarefas
                  </summary>
                  <div className="space-y-3">
                    {tasks.map((entry) => (
                      <label
                        key={entry.id}
                        className="flex min-h-12 items-center gap-3"
                      >
                        <input
                          type="checkbox"
                          className="h-5 w-5 shrink-0 accent-amber-400"
                          checked={selected.includes(entry.id)}
                          onChange={(event) =>
                            props.setSelected(
                              event.target.checked
                                ? [...selected, entry.id]
                                : selected.filter((id) => id !== entry.id),
                            )
                          }
                        />
                        <span className="break-words">
                          #{entry.order_code || entry.order_id.slice(0, 8)} ·{" "}
                          {entry.product_name} · {entry.unit_index}
                        </span>
                      </label>
                    ))}
                  </div>
                </details>
              )}
              {selected.length > 0 && (
                <>
                  <p>{selected.length} tarefa(s) selecionada(s)</p>
                  <select
                    aria-label="Operador de destino"
                    value={targetOperator}
                    onChange={(event) =>
                      props.setTargetOperator(event.target.value)
                    }
                    className="min-h-12 w-full min-w-0 rounded-xl border border-[#30485d] bg-[#07111c] px-2"
                  >
                    <option value="">Escolha o operador</option>
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
                          {operator.operator_name} ·{" "}
                          {presenceLabels[operator.state]}
                        </option>
                      ))}
                  </select>
                  <button
                    type="button"
                    className={`${control} w-full`}
                    disabled={!targetOperator || Boolean(busy)}
                    onClick={() => void props.redistribute()}
                  >
                    {busy === "redistribute" ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <Users size={18} />
                    )}
                    Redistribuir
                  </button>
                </>
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
