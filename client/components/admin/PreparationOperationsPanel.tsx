import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ChefHat, ClipboardList, Loader2, Play, RefreshCw, Square, TriangleAlert } from "lucide-react";
import { preparationApi, type PreparationOrder, type PreparationRecipe } from "@/lib/api";

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

function OrderCard({ order, onRefresh }: { order: PreparationOrder; onRefresh: () => Promise<void> }) {
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
    try { await action(); setMessage(success); await onRefresh(); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel executar a operacao."); } finally { setBusy(false); }
  }

  const canStart = ["approved", "scheduled", "paused"].includes(order.state);
  const canReport = ["in_progress", "partially_completed"].includes(order.state);
  const canComplete = canReport && Number(order.remaining_quantity) === 0;

  return (
    <article className={box}>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2"><ChefHat size={17} className="text-gold" /><h3 className="font-black text-cream">{order.name}</h3></div>
          <p className="mt-1 text-xs text-stone">Meta {order.target_quantity} {order.output_unit_name ?? order.output_unit_id} · produzido {order.produced_total} · restante {order.remaining_quantity}</p>
          <p className="mt-1 text-xs font-bold text-gold">{stateLabel(order.state)} · versao {order.version}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={ghost} disabled={busy} onClick={() => run(() => preparationApi.recipe(order.id).then(setRecipe), "Ficha carregada.")}><ClipboardList size={15} /> Ficha</button>
          {canStart && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.start(order.id, order.version, key("start", order.id)), "Preparo iniciado.")}><Play size={15} /> Iniciar</button>}
          {canComplete && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.complete(order.id, order.version, key("complete", order.id)), "Preparo concluido.")}><CheckCircle2 size={15} /> Concluir</button>}
        </div>
      </div>

      {recipe && <div className="mt-4 rounded-lg border border-surface-03 bg-surface-01 p-3 text-sm">
        <p className={recipe.executable ? "font-bold text-emerald-300" : "font-bold text-amber-300"}>{recipe.executable ? "Ficha executavel" : "Ficha pendente"}</p>
        {recipe.instructions && <p className="mt-2 text-stone">{recipe.instructions}</p>}
        {recipe.warnings.map((warning) => <p key={`${warning.code}-${warning.message}`} className="mt-2 flex gap-2 text-amber-200"><TriangleAlert size={15} /> {warning.message}</p>)}
        <div className="mt-3 grid gap-2 sm:grid-cols-2">{recipe.ingredients.map((item) => <div key={`${item.inventory_item_id}-${item.unit_id}`} className="rounded bg-surface-02 px-2 py-1 text-xs text-stone">{item.inventory_item_name ?? item.inventory_item_id}: <b className="text-cream">{item.quantity} {item.unit_symbol ?? item.unit_id}</b></div>)}</div>
      </div>}

      {canReport && <div className="mt-4 grid gap-2 md:grid-cols-4">
        <input className={input} inputMode="decimal" placeholder="Produzido" value={produced} onChange={(e) => setProduced(e.target.value)} />
        <input className={input} inputMode="decimal" placeholder="Aprovado" value={approved} onChange={(e) => setApproved(e.target.value)} />
        <input className={input} inputMode="decimal" placeholder="Descartado" value={discarded} onChange={(e) => setDiscarded(e.target.value)} />
        <button type="button" className={button} disabled={busy || !produced || !approved} onClick={() => run(() => preparationApi.report(order.id, { expected_version: order.version, produced_quantity: produced, approved_quantity: approved, discarded_quantity: discarded, input_allocations: [], losses: [], reason: reason || null, prepared_at: new Date().toISOString() }, key("report", order.id)), "Apontamento registrado.")}><Square size={15} /> Apontar</button>
        <input className={`${input} md:col-span-4`} placeholder="Motivo de perda ou descarte (obrigatorio quando aplicavel)" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>}
      {message && <p className="mt-3 text-sm font-semibold text-emerald-300">{message}</p>}
      {error && <p className="mt-3 flex gap-2 text-sm font-semibold text-red-300"><AlertTriangle size={16} /> {error}</p>}
    </article>
  );
}

export default function PreparationOperationsPanel() {
  const [orders, setOrders] = useState<PreparationOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<"operator" | "planning">("operator");
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [unit, setUnit] = useState("");
  const [plannedFor, setPlannedFor] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const load = async () => {
    setLoading(true); setError("");
    try { setOrders(listValue(await preparationApi.listOrders())); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel carregar os preparos."); } finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const activeOrders = useMemo(() => orders.filter((order) => !["completed", "cancelled"].includes(order.state)), [orders]);
  async function createOrder() {
    setSaving(true); setMessage(""); setError("");
    try { await preparationApi.create({ name, target_quantity: target, output_unit_id: unit, planned_for: plannedFor || null }, key("create", name)); setName(""); setTarget(""); setUnit(""); setPlannedFor(""); setMessage("Ordem de preparo criada."); await load(); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel criar a ordem."); } finally { setSaving(false); }
  }

  return <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div><h2 className="text-lg font-black text-cream">Preparo e planejamento</h2><p className="mt-1 text-sm text-stone">Ordens, fichas e apontamentos de producao com controle de versao.</p></div>
      <div className="flex flex-wrap gap-2"><button type="button" className={view === "operator" ? button : ghost} onClick={() => setView("operator")}>Operacao</button><button type="button" className={view === "planning" ? button : ghost} onClick={() => setView("planning")}>Planejamento</button><button type="button" className={ghost} onClick={() => void load()}><RefreshCw size={15} /> Atualizar</button></div>
    </div>
    {loading && <div className="flex min-h-32 items-center justify-center text-stone"><Loader2 size={18} className="mr-2 animate-spin" /> Carregando ordens...</div>}
    {!loading && view === "operator" && <div className="space-y-3">{activeOrders.length === 0 ? <p className="rounded-lg border border-dashed border-surface-03 p-6 text-center text-sm text-stone">Nenhuma ordem de preparo pendente.</p> : activeOrders.map((order) => <OrderCard key={order.id} order={order} onRefresh={load} />)}</div>}
    {!loading && view === "planning" && <div className="space-y-4">
      <div className={box}><h3 className="font-black text-cream">Nova ordem</h3><div className="mt-3 grid gap-3 md:grid-cols-4"><input className={input} placeholder="Nome da preparacao" value={name} onChange={(e) => setName(e.target.value)} /><input className={input} inputMode="decimal" placeholder="Quantidade alvo" value={target} onChange={(e) => setTarget(e.target.value)} /><input className={input} placeholder="Unidade de saida" value={unit} onChange={(e) => setUnit(e.target.value)} /><input className={input} type="date" value={plannedFor} onChange={(e) => setPlannedFor(e.target.value)} /><button type="button" className={`${button} md:col-span-4`} disabled={saving || !name || !target || !unit} onClick={() => void createOrder()}>Criar ordem de preparo</button></div></div>
      {orders.length === 0 ? <p className="rounded-lg border border-dashed border-surface-03 p-6 text-center text-sm text-stone">Nenhuma ordem cadastrada.</p> : orders.map((order) => <OrderCard key={order.id} order={order} onRefresh={load} />)}
    </div>}
    {message && <p className="text-sm font-semibold text-emerald-300">{message}</p>}
    {error && <p className="flex gap-2 text-sm font-semibold text-red-300"><AlertTriangle size={16} /> {error}</p>}
  </section>;
}
