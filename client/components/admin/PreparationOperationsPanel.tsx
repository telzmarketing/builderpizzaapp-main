import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ChefHat, ClipboardList, Loader2, Play, RefreshCw, Square, TriangleAlert } from "lucide-react";
import { preparationApi, type PreparationOrder, type PreparationRecipe } from "@/lib/api";
import { PreparationLabelPrintDialog } from "@/components/kds/LabelPrintDialog";
import PcpWeeklyPanel from "@/components/admin/PcpWeeklyPanel";

const box = "rounded-lg border border-surface-03 bg-surface-02 p-4";
const input = "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold";
const button = "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-50";
const ghost = "inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone hover:bg-surface-03 hover:text-cream disabled:opacity-50";

function key(prefix: string, id: string) {
  return `${prefix}:${id}:${Date.now()}`;
}

function listValue(value: PreparationOrder[] | { items: PreparationOrder[] }) {
  return Array.isArray(value) ? value : value.items;
}

function stateLabel(state: string) {
  return ({ draft: "Rascunho", approved: "Aprovado", scheduled: "Programado", in_progress: "Em preparo", partially_completed: "Parcial", completed: "Concluido", paused: "Pausado", blocked: "Bloqueado", cancelled: "Cancelado" } as Record<string, string>)[state] ?? state;
}

function OrderCard({ order, onRefresh, onExecution }: { order: PreparationOrder; onRefresh: () => Promise<void>; onExecution: (id: string) => void }) {
  const [recipe, setRecipe] = useState<PreparationRecipe | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [produced, setProduced] = useState("");
  const [approved, setApproved] = useState("");
  const [discarded, setDiscarded] = useState("0");
  const [reason, setReason] = useState("");

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(""); setMessage("");
    try { const result = await action(); if (result && typeof result === "object" && "execution_id" in result && typeof result.execution_id === "string") onExecution(result.execution_id); setMessage(success); await onRefresh(); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel executar a operacao."); } finally { setBusy(false); }
  }

  const canStart = ["waiting", "scheduled"].includes(order.state);
  const canReport = ["in_progress", "partially_completed"].includes(order.state);
  const canComplete = canReport && order.remaining_quantity != null && Number(order.remaining_quantity) === 0;

  return (
    <article className={box}>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2"><ChefHat size={17} className="text-gold" /><h3 className="font-black text-cream">{order.name}</h3></div>
          <p className="mt-1 text-xs text-stone">Meta {order.target_quantity || "Não informada"} {order.output_unit_name || ""} · produzido {order.produced_total} · restante {order.remaining_quantity ?? "Não informado"}</p>
          {order.scheduled_for && <p className="mt-1 text-xs text-stone">Programado: {new Date(order.scheduled_for).toLocaleString("pt-BR")}</p>}
          {order.pending_fields?.length ? <p role="status" className="mt-2 text-sm font-bold text-amber-200">Pendências: {order.pending_fields.join(", ")}</p> : null}
          <p className="mt-1 text-xs font-bold text-gold">{stateLabel(order.state)} · versao {order.version}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={ghost} disabled={busy} onClick={() => run(() => preparationApi.recipe(order.id).then(setRecipe), "Ficha carregada.")}><ClipboardList size={15} /> Ficha</button>
          {canStart && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.start(order.id, order.version, key("start", order.id)), "Preparo iniciado.")}><Play size={15} /> Iniciar</button>}
          {order.state === "paused" && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.command(order.id, "resume", { expected_version: order.version }, key("resume", order.id)), "Preparo retomado.")}><Play size={15} /> Retomar</button>}
          {canReport && <button type="button" className={ghost} disabled={busy} onClick={() => run(() => preparationApi.command(order.id, "pause", { expected_version: order.version }, key("pause", order.id)), "Preparo pausado.")}>Pausar</button>}
          {canComplete && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.complete(order.id, order.version, key("complete", order.id)), "Preparo concluido.")}><CheckCircle2 size={15} /> Concluir</button>}
        </div>
      </div>

      {recipe && <div className="mt-4 rounded-lg border border-surface-03 bg-surface-01 p-3 text-sm">
        <p className={recipe.executable ? "font-bold text-emerald-300" : "font-bold text-amber-300"}>{recipe.executable ? "Ficha executavel" : "Ficha pendente"}</p>
        {recipe.instructions && <p className="mt-2 text-stone">{recipe.instructions}</p>}
        {(recipe.warnings ?? []).map((warning) => <p key={`${warning.code}-${warning.message}`} className="mt-2 flex gap-2 text-amber-200"><TriangleAlert size={15} /> {warning.message}</p>)}
        <div className="mt-3 grid gap-2 sm:grid-cols-2">{(recipe.ingredients ?? []).map((item) => <div key={`${item.inventory_item_id}-${item.unit_id}`} className="rounded bg-surface-02 px-2 py-1 text-xs text-stone">{item.inventory_item_name || "Insumo sem identificação"}: <b className="text-cream">{item.quantity} {item.unit_symbol || ""}</b></div>)}</div>
      </div>}

      {canReport && <div className="mt-4 grid gap-2 md:grid-cols-4">
        <input className={input} inputMode="decimal" placeholder="Produzido" value={produced} onChange={(e) => setProduced(e.target.value)} />
        <input className={input} inputMode="decimal" placeholder="Aprovado" value={approved} onChange={(e) => setApproved(e.target.value)} />
        <input className={input} inputMode="decimal" placeholder="Descartado" value={discarded} onChange={(e) => setDiscarded(e.target.value)} />
        <button type="button" className={button} disabled={busy || !produced || !approved || !recipe?.executable} onClick={() => run(() => preparationApi.report(order.id, { expected_version: order.version, produced_quantity: produced, approved_quantity: approved, discarded_quantity: discarded, input_allocations: [], losses: [], reason: reason || null, prepared_at: new Date().toISOString() }, key("report", order.id)), "Apontamento registrado.")}><Square size={15} /> Apontar</button>
        {!recipe?.executable && <p className="text-sm text-amber-200 md:col-span-4">Carregue uma ficha executável antes de confirmar a produção.</p>}
        <input className={`${input} md:col-span-4`} placeholder="Motivo de perda ou descarte (obrigatorio quando aplicavel)" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>}
      {message && <p className="mt-3 text-sm font-semibold text-emerald-300">{message}</p>}
      {error && <p className="mt-3 flex gap-2 text-sm font-semibold text-red-300"><AlertTriangle size={16} /> {error}</p>}
    </article>
  );
}

export default function PreparationOperationsPanel({ showKdsLink = true }: { showKdsLink?: boolean }) {
  const [orders, setOrders] = useState<PreparationOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<"operator" | "planning">("operator");
  const [recipeId, setRecipeId] = useState("");
  const [target, setTarget] = useState("");
  const [plannedFor, setPlannedFor] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [labelsOpen, setLabelsOpen] = useState(false);

  const load = async () => {
    setLoading(true); setError("");
    try { setOrders(listValue(await preparationApi.listOrders())); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel carregar os preparos."); } finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const activeOrders = useMemo(() => orders.filter((order) => !["completed", "cancelled"].includes(order.state)), [orders]);
  const knownRecipes = useMemo(() => [...new Map(orders.filter((order) => order.recipe_id).map((order) => [order.recipe_id!, { id: order.recipe_id!, name: order.name }])).values()], [orders]);
  async function createOrder() {
    setSaving(true); setMessage(""); setError("");
    try { await preparationApi.create({ recipe_id: recipeId, target_quantity: target, scheduled_for: plannedFor ? new Date(plannedFor).toISOString() : null, expected_version: 0 }, key("create", recipeId)); setRecipeId(""); setTarget(""); setPlannedFor(""); setMessage("Ordem de preparo criada."); await load(); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel criar a ordem."); } finally { setSaving(false); }
  }

  return <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div><h2 className="text-lg font-black text-cream">Preparo e planejamento</h2><p className="mt-1 text-sm text-stone">Ordens, fichas e apontamentos de producao com controle de versao.</p></div>
      {showKdsLink && <Link to="/painel/preparo" className={ghost}>Abrir KDS Cozinha Preparo</Link>}
      <div className="flex flex-wrap gap-2"><button type="button" className={view === "operator" ? button : ghost} onClick={() => setView("operator")}>Operacao</button><button type="button" className={view === "planning" ? button : ghost} onClick={() => setView("planning")}>Planejamento</button><button type="button" className={ghost} onClick={() => void load()}><RefreshCw size={15} /> Atualizar</button></div>
    </div>
    {loading && <div className="flex min-h-32 items-center justify-center text-stone"><Loader2 size={18} className="mr-2 animate-spin" /> Carregando ordens...</div>}
    {executionId && <button type="button" className={ghost} onClick={() => setLabelsOpen(true)}>Etiquetas do último preparo</button>}
    <PreparationLabelPrintDialog executionId={executionId} open={labelsOpen} onOpenChange={setLabelsOpen} />
    {!loading && view === "operator" && <div className="space-y-3">{activeOrders.length === 0 ? <p className="rounded-lg border border-dashed border-surface-03 p-6 text-center text-sm text-stone">Nenhuma ordem de preparo pendente.</p> : activeOrders.map((order) => <OrderCard key={order.id} order={order} onRefresh={load} onExecution={(id) => { setExecutionId(id); setLabelsOpen(true); }} />)}</div>}
    {!loading && view === "planning" && <div className="space-y-4">
      <PcpWeeklyPanel />
      <div className={box}><h3 className="font-black text-cream">Nova ordem por ficha cadastrada</h3>{knownRecipes.length ? <div className="mt-3 grid gap-3 md:grid-cols-3"><label className="text-sm">Ficha técnica<select className={input} value={recipeId} onChange={(event) => setRecipeId(event.target.value)}><option value="">Selecionar ficha</option>{knownRecipes.map((recipe) => <option key={recipe.id} value={recipe.id}>{recipe.name}</option>)}</select></label><label className="text-sm">Quantidade planejada<input className={input} inputMode="decimal" value={target} onChange={(event) => setTarget(event.target.value)} /></label><label className="text-sm">Data e horário<input className={input} type="datetime-local" value={plannedFor} onChange={(event) => setPlannedFor(event.target.value)} /></label><button type="button" className={`${button} md:col-span-3`} disabled={saving || !recipeId || !target} onClick={() => void createOrder()}>Criar ordem de preparo</button></div> : <p className="mt-3 text-sm text-stone">Nenhuma ficha operacional foi disponibilizada. Cadastre e valide a ficha antes de programar um preparo.</p>}</div>
      {orders.length === 0 ? <p className="rounded-lg border border-dashed border-surface-03 p-6 text-center text-sm text-stone">Nenhuma ordem cadastrada.</p> : orders.map((order) => <OrderCard key={order.id} order={order} onRefresh={load} onExecution={(id) => { setExecutionId(id); setLabelsOpen(true); }} />)}
    </div>}
    {message && <p className="text-sm font-semibold text-emerald-300">{message}</p>}
    {error && <p className="flex gap-2 text-sm font-semibold text-red-300"><AlertTriangle size={16} /> {error}</p>}
  </section>;
}
