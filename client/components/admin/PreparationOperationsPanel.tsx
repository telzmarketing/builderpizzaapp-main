import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ChefHat, ClipboardList, Loader2, Play, RefreshCw, Square, TriangleAlert } from "lucide-react";
import { inventoryApi, inventoryFoundationApi, preparationApi, type FoundationLot, type InventoryOverview, type PreparationInputAllocation, type PreparationOrder, type PreparationRecipe, type PreparationRecipeDefinition } from "@/lib/api";
import { PreparationLabelPrintDialog } from "@/components/kds/LabelPrintDialog";
import PcpWeeklyPanel from "@/components/admin/PcpWeeklyPanel";

const box = "preparation-card rounded-xl border border-surface-03 bg-surface-02 p-4 shadow-lg shadow-black/10";
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

export interface PreparationAllocationDraft {
  id: string;
  ingredientIndex: number;
  item_id: string;
  unit_id: string;
  quantity: string;
  location_id: string;
  lot_id: string | null;
}

export function buildPreparationAllocationDrafts(
  recipe: PreparationRecipe,
  inventory: InventoryOverview | null,
  lots: FoundationLot[],
): PreparationAllocationDraft[] {
  return (recipe.ingredients ?? []).map((ingredient, ingredientIndex) => {
    const item = inventory?.items.find((candidate) => candidate.id === ingredient.inventory_item_id);
    const recipeLot = ingredient.lot_id ? lots.find((lot) => lot.id === ingredient.lot_id) : null;
    return {
      id: `ingredient-${ingredientIndex}`,
      ingredientIndex,
      item_id: ingredient.inventory_item_id,
      unit_id: ingredient.unit_id,
      quantity: String(ingredient.quantity ?? ""),
      location_id: recipeLot?.location_id ?? item?.default_location_id ?? "",
      lot_id: recipeLot?.id ?? null,
    };
  });
}

export function preparationAllocationPayload(drafts: PreparationAllocationDraft[]): PreparationInputAllocation[] {
  return drafts.map(({ item_id, unit_id, quantity, location_id, lot_id }) => ({ item_id, unit_id, quantity, location_id, lot_id }));
}

export function validatePreparationAllocationDrafts(drafts: PreparationAllocationDraft[]): string | null {
  if (!drafts.length) return "Carregue uma ficha com ao menos um ingrediente.";
  if (drafts.some((draft) => !draft.item_id || !draft.unit_id)) return "A ficha possui um ingrediente sem item ou unidade.";
  if (drafts.some((draft) => !draft.location_id)) return "Selecione o local de cada ingrediente.";
  if (drafts.some((draft) => !draft.quantity.trim() || !Number.isFinite(Number(draft.quantity.replace(",", "."))) || Number(draft.quantity.replace(",", ".")) <= 0)) return "Informe quantidades positivas para todos os ingredientes.";
  return null;
}

function OrderCard({ order, onRefresh, onExecution }: { order: PreparationOrder; onRefresh: () => Promise<void>; onExecution: (id: string) => void }) {
  const [recipe, setRecipe] = useState<PreparationRecipe | null>(null);
  const [inventory, setInventory] = useState<InventoryOverview | null>(null);
  const [lots, setLots] = useState<FoundationLot[]>([]);
  const [allocationDrafts, setAllocationDrafts] = useState<PreparationAllocationDraft[]>([]);
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

  const canStart = ["waiting", "scheduled"].includes(order.status);
  const canReport = ["in_progress", "partially_completed"].includes(order.status);
  const canComplete = canReport && Number(order.produced_quantity) + Number(order.lost_quantity) + Number(order.discarded_quantity) === Number(order.target_quantity);
  const allocationError = validatePreparationAllocationDrafts(allocationDrafts);

  async function loadRecipeAndStock() {
    const [nextRecipe, nextInventory, nextLots] = await Promise.all([
      preparationApi.recipe(order.id),
      inventoryApi.overview(),
      inventoryFoundationApi.lots(),
    ]);
    setRecipe(nextRecipe);
    setInventory(nextInventory);
    setLots(nextLots.items);
    setAllocationDrafts(buildPreparationAllocationDrafts(nextRecipe, nextInventory, nextLots.items));
  }

  function updateAllocation(id: string, patch: Partial<PreparationAllocationDraft>) {
    setAllocationDrafts((current) => current.map((draft) => draft.id === id ? { ...draft, ...patch } : draft));
  }

  function addAllocation(ingredientIndex: number) {
    const source = allocationDrafts.find((draft) => draft.ingredientIndex === ingredientIndex);
    if (!source) return;
    setAllocationDrafts((current) => [...current, {
      ...source,
      id: `${source.id}-extra-${Date.now()}`,
      quantity: "",
      lot_id: null,
    }]);
  }

  function removeAllocation(id: string) {
    setAllocationDrafts((current) => {
      const draft = current.find((candidate) => candidate.id === id);
      if (!draft || current.filter((candidate) => candidate.ingredientIndex === draft.ingredientIndex).length <= 1) return current;
      return current.filter((candidate) => candidate.id !== id);
    });
  }

  const itemName = (itemId: string) => inventory?.items.find((item) => item.id === itemId)?.name || itemId;
  const locationName = (locationId: string) => inventory?.locations.find((location) => location.id === locationId)?.name || locationId;

  return (
    <article className={`${box} preparation-order-card`}>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2"><ChefHat size={17} className="text-gold" /><h3 className="font-black text-cream">{order.recipe_id}</h3></div>
          <p className="mt-1 text-xs text-stone">Meta {order.target_quantity} · produzido {order.produced_quantity} · perdas {order.lost_quantity} · descartado {order.discarded_quantity}</p>
          <p className="mt-1 text-xs font-bold text-gold">{stateLabel(order.status)} · versão {order.version}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={ghost} disabled={busy} onClick={() => run(loadRecipeAndStock, "Ficha e saldos carregados.")}><ClipboardList size={15} /> Ficha</button>
          {order.status === "draft" && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.manage(order.id, "approve", { expected_version: order.version }, key("approve", order.id)), "Ordem aprovada e reservada.")}>Aprovar</button>}
          {order.status === "approved" && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.manage(order.id, "schedule", { expected_version: order.version }, key("schedule", order.id)), "Ordem enviada ao KDS.")}>Enviar ao KDS</button>}
          {canStart && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.start(order.id, order.version, key("start", order.id)), "Preparo iniciado.")}><Play size={15} /> Iniciar</button>}
          {order.status === "paused" && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.command(order.id, "resume", { expected_version: order.version }, key("resume", order.id)), "Preparo retomado.")}><Play size={15} /> Retomar</button>}
          {canReport && <button type="button" className={ghost} disabled={busy} onClick={() => run(() => preparationApi.command(order.id, "pause", { expected_version: order.version }, key("pause", order.id)), "Preparo pausado.")}>Pausar</button>}
          {canComplete && <button type="button" className={button} disabled={busy} onClick={() => run(() => preparationApi.complete(order.id, order.version, key("complete", order.id)), "Preparo concluido.")}><CheckCircle2 size={15} /> Concluir</button>}
        </div>
      </div>

      {recipe && <div className="mt-4 rounded-lg border border-surface-03 bg-surface-01 p-3 text-sm">
        <p className={recipe.executable ? "font-bold text-emerald-300" : "font-bold text-amber-300"}>{recipe.executable ? "Ficha executavel" : "Ficha pendente"}</p>
        {recipe.instructions && <p className="mt-2 text-stone">{recipe.instructions}</p>}
        {(recipe.warnings ?? []).map((warning) => <p key={`${warning.code}-${warning.message}`} className="mt-2 flex gap-2 text-amber-200"><TriangleAlert size={15} /> {warning.message}</p>)}
        <div className="mt-3 grid gap-2 sm:grid-cols-2">{(recipe.ingredients ?? []).map((item, index) => <div key={`${item.inventory_item_id}-${item.unit_id}-${index}`} className="rounded bg-surface-02 px-2 py-1 text-xs text-stone">{item.inventory_item_name || itemName(item.inventory_item_id) || "Insumo sem identificação"}: <b className="text-cream">{item.quantity} {item.unit_symbol || ""}</b></div>)}</div>
      </div>}

      {canReport && <div className="mt-4 grid gap-2 md:grid-cols-4">
        <input className={input} inputMode="decimal" placeholder="Produzido" value={produced} onChange={(e) => setProduced(e.target.value)} />
        <input className={input} inputMode="decimal" placeholder="Aprovado" value={approved} onChange={(e) => setApproved(e.target.value)} />
        <input className={input} inputMode="decimal" placeholder="Descartado" value={discarded} onChange={(e) => setDiscarded(e.target.value)} />
        <button type="button" className={button} disabled={busy || !produced || !approved || !recipe?.executable || Boolean(allocationError)} onClick={() => run(() => { const inputAllocations = preparationAllocationPayload(allocationDrafts); const validationError = validatePreparationAllocationDrafts(allocationDrafts); if (validationError) throw new Error(validationError); return preparationApi.report(order.id, { expected_version: order.version, produced_quantity: produced, approved_quantity: approved, discarded_quantity: discarded, input_allocations: inputAllocations, losses: [], reason: reason || null, prepared_at: new Date().toISOString() }, key("report", order.id)); }, "Apontamento registrado.")}><Square size={15} /> Apontar</button>
        {!recipe?.executable && <p className="text-sm text-amber-200 md:col-span-4">Carregue uma ficha executável antes de confirmar a produção.</p>}
        {recipe?.executable && <div className="md:col-span-4 rounded-lg border border-surface-03 bg-surface-01 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="font-bold text-cream">Consumo por ingrediente</p><p className="text-xs text-stone">Informe a quantidade efetivamente consumida e selecione o local e, quando houver, o lote.</p></div>{allocationError && <p className="text-xs font-semibold text-amber-200">{allocationError}</p>}</div>
          <div className="mt-3 space-y-3">
            {allocationDrafts.map((draft) => {
              const ingredient = recipe.ingredients[draft.ingredientIndex];
              const itemLots = lots.filter((lot) => lot.item_id === draft.item_id && lot.status === "available" && (!draft.location_id || lot.location_id === draft.location_id));
              return <div key={draft.id} className="grid gap-2 rounded-lg border border-surface-03 bg-surface-02 p-2 md:grid-cols-[minmax(0,1.4fr)_minmax(7rem,0.8fr)_minmax(10rem,1fr)_minmax(10rem,1fr)_auto] md:items-end">
                <div><p className="text-xs font-bold text-cream">{ingredient?.inventory_item_name || itemName(draft.item_id)}</p><p className="text-xs text-stone">Ficha: {ingredient?.quantity} {ingredient?.unit_symbol || ""} · unidade {ingredient?.unit_id || draft.unit_id}</p></div>
                <label className="text-xs text-stone">Quantidade<input aria-label={`Quantidade ${itemName(draft.item_id)}`} className={input} inputMode="decimal" value={draft.quantity} onChange={(event) => updateAllocation(draft.id, { quantity: event.target.value })} /></label>
                <label className="text-xs text-stone">Local<select aria-label={`Local ${itemName(draft.item_id)}`} className={input} value={draft.location_id} onChange={(event) => updateAllocation(draft.id, { location_id: event.target.value, lot_id: null })}><option value="">Selecionar local</option>{(inventory?.locations ?? []).filter((location) => location.active).map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
                <label className="text-xs text-stone">Lote<select aria-label={`Lote ${itemName(draft.item_id)}`} className={input} value={draft.lot_id ?? ""} onChange={(event) => updateAllocation(draft.id, { lot_id: event.target.value || null })}><option value="">Sem lote rastreado</option>{itemLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.lot_code} · {locationName(lot.location_id)}</option>)}</select></label>
                <div className="flex gap-2"><button type="button" className={ghost} onClick={() => addAllocation(draft.ingredientIndex)} aria-label="Adicionar outro local ou lote">+ lote/local</button><button type="button" className={ghost} disabled={allocationDrafts.filter((candidate) => candidate.ingredientIndex === draft.ingredientIndex).length <= 1} onClick={() => removeAllocation(draft.id)} aria-label="Remover alocação">Remover</button></div>
              </div>;
            })}
          </div>
        </div>}
        <input className={`${input} md:col-span-4`} placeholder="Motivo de perda ou descarte (obrigatorio quando aplicavel)" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>}
      {message && <p className="mt-3 text-sm font-semibold text-emerald-300">{message}</p>}
      {error && <p className="mt-3 flex gap-2 text-sm font-semibold text-red-300"><AlertTriangle size={16} /> {error}</p>}
    </article>
  );
}

export default function PreparationOperationsPanel({ showKdsLink = true }: { showKdsLink?: boolean }) {
  const [orders, setOrders] = useState<PreparationOrder[]>([]);
  const [operationalRecipes, setOperationalRecipes] = useState<PreparationRecipeDefinition[]>([]);
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
    try { const [orderResult, recipes] = await Promise.all([preparationApi.listOrders(), preparationApi.listRecipes()]); setOrders(listValue(orderResult)); setOperationalRecipes(recipes); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel carregar os preparos."); } finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const activeOrders = useMemo(() => orders.filter((order) => !["completed", "cancelled"].includes(order.status)), [orders]);
  const knownRecipes = useMemo(() => operationalRecipes, [operationalRecipes]);
  async function createOrder() {
    setSaving(true); setMessage(""); setError("");
    try { await preparationApi.create({ recipe_id: recipeId, target_quantity: target, scheduled_for: plannedFor ? new Date(plannedFor).toISOString() : null, expected_version: 0 }, key("create", recipeId)); setRecipeId(""); setTarget(""); setPlannedFor(""); setMessage("Ordem de preparo criada."); await load(); } catch (err) { setError(err instanceof Error ? err.message : "Nao foi possivel criar a ordem."); } finally { setSaving(false); }
  }

  return <section className="preparation-panel space-y-5 rounded-xl border border-surface-03 bg-surface-02 p-4 shadow-2xl shadow-black/15 sm:p-5">
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
