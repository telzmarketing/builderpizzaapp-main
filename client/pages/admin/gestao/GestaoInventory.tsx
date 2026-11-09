import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ChefHat, Database, Layers3, Loader2, Package, Pencil, Plus, RefreshCw, Settings, ShoppingCart, Trash2, Truck } from "lucide-react";
import { AdminPageTabs, type AdminPageTab } from "@/components/admin/AdminPageChrome";
import AdminGestao from "./AdminGestao";
import InventoryFoundationPanel from "@/components/admin/InventoryFoundationPanel";
import InventoryUnitClassificationPanel from "@/components/admin/InventoryUnitClassificationPanel";
import InventoryReceiptDocumentsPanel from "@/components/admin/InventoryReceiptDocumentsPanel";
import PreparationOperationsPanel from "@/components/admin/PreparationOperationsPanel";
import InventoryPortioningPanel from "@/components/admin/InventoryPortioningPanel";
import InventoryPortionStockPanel from "@/components/admin/InventoryPortionStockPanel";
import InventoryStockAdjustmentDialog, { hasUnresolvedAdjustment, type AdjustmentItem } from "@/components/admin/InventoryStockAdjustmentDialog";
import { filterAndSort, InventoryTableControls } from "@/components/admin/InventoryTableControls";
import {
  inventoryApi,
  type InventoryCategory,
  type InventoryItem,
  type InventoryLocation,
  type InventoryManualEntry,
  type InventoryOverview,
  type InventoryPurchase,
  type InventoryPurchaseItem,
  type InventorySupplier,
  type InventoryUnit,
} from "@/lib/api";
import { formatQuantity } from "@/lib/formatQuantity";

type Section = "settings" | "items" | "ingredient-stock" | "portioning" | "portion-stock" | "replenishment" | "foundation" | "purchases" | "entries" | "suppliers" | "preparation" | "base";
type InventoryGroup = "cadastro" | "estoque" | "producao" | "operacao";

const inventoryRouteBase = "/painel/gestao/estoque";
const sectionSlugs: Record<Section, string> = {
  items: "insumos",
  "ingredient-stock": "estoque-insumos",
  portioning: "porcionamento",
  "portion-stock": "estoque-porcionamento",
  replenishment: "reposicao",
  foundation: "saldos-conversoes",
  purchases: "compras",
  entries: "entradas",
  suppliers: "fornecedores",
  preparation: "preparo",
  base: "base",
  settings: "configuracoes",
};

const inventoryGroups: AdminPageTab<InventoryGroup>[] = [
  { id: "cadastro", label: "Cadastro", icon: Package },
  { id: "estoque", label: "Estoque", icon: Database },
  { id: "producao", label: "Produção", icon: ChefHat },
  { id: "operacao", label: "Operação", icon: Settings },
];

const groupSections: Record<InventoryGroup, Section[]> = {
  cadastro: ["items", "portioning", "suppliers", "base"],
  estoque: ["ingredient-stock", "portion-stock", "foundation"],
  producao: ["preparation"],
  operacao: ["replenishment", "purchases", "entries", "settings"],
};

const sectionGroup = (section: Section): InventoryGroup => (
  (Object.entries(groupSections).find(([, sections]) => sections.includes(section))?.[0] as InventoryGroup | undefined) ?? "cadastro"
);

function sectionFromPath(pathname: string): Section | null {
  const slug = pathname.replace(`${inventoryRouteBase}/`, "").replace(/\/$/, "");
  if (!slug || slug === pathname) return null;
  const entry = (Object.entries(sectionSlugs) as Array<[Section, string]>).find(([, value]) => value === slug);
  return entry?.[0] ?? null;
}

const sections: AdminPageTab<Section>[] = [
  { id: "items", label: "Insumos", icon: Package },
  { id: "ingredient-stock", label: "Estoque de Insumos", icon: Database },
  { id: "portioning", label: "Porcionamento", icon: Package },
  { id: "portion-stock", label: "Estoque de Porcionamento", icon: Database },
  { id: "replenishment", label: "Reposição", icon: AlertTriangle },
  { id: "foundation", label: "Saldos e Conversões", icon: Layers3 },
  { id: "purchases", label: "Compras", icon: ShoppingCart },
  { id: "entries", label: "Entradas", icon: Database },
  { id: "suppliers", label: "Fornecedores", icon: Truck },
  { id: "preparation", label: "Preparo", icon: ChefHat },
  { id: "base", label: "Base", icon: Layers3 },
  { id: "settings", label: "Configurações", icon: Settings },
];

const sectionContent: Record<Section, { title: string; description: string }> = {
  items: { title: "Cadastro de Insumos", description: "Cadastre os insumos, embalagens e materiais usados pelo estoque." },
  "ingredient-stock": { title: "Estoque de Insumos", description: "Consulte os saldos atuais, mínimos e locais dos insumos cadastrados." },
  portioning: { title: "Cadastro de Porcionamento", description: "Configure como cada insumo será transformado em porções para uso." },
  "portion-stock": { title: "Estoque de Porcionamento", description: "Consulte as porções disponíveis e solicite novos porcionamentos." },
  replenishment: { title: "Reposição de Estoque", description: "Identifique os insumos abaixo do mínimo e gere uma solicitação de compra." },
  foundation: { title: "Base do Estoque", description: "Cadastre unidades, categorias, locais e conversões usadas pelo estoque." },
  purchases: { title: "Compras de Estoque", description: "Crie, revise e confirme compras de insumos sem alterar o saldo antes da entrada." },
  entries: { title: "Entradas e Movimentos de Estoque", description: "Registre entradas, saídas e ajustes manuais com motivo e observações." },
  suppliers: { title: "Cadastro de Fornecedores", description: "Cadastre e mantenha os fornecedores utilizados nas compras de estoque." },
  preparation: { title: "Preparo de Porcionamento", description: "Acompanhe as solicitações, consulte a ficha e registre o porcionamento efetuado." },
  base: { title: "Base do Estoque", description: "Cadastre as estruturas auxiliares que sustentam os controles de estoque." },
  settings: { title: "Configurações do Estoque", description: "Configure as opções gerais do módulo de estoque." },
};

const emptyOverview: InventoryOverview = {
  units: [],
  categories: [],
  locations: [],
  suppliers: [],
  items: [],
  purchases: [],
  manual_entries: [],
  movements: [],
  balances: [],
};

const inputClass = "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none transition placeholder:text-stone/70 focus:border-gold";
const buttonClass = "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60";
const ghostButtonClass = "inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone transition hover:bg-surface-03 hover:text-cream";

function currency(value: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

const quantity = (value: number | string | null | undefined) => formatQuantity(value, "0");

export default function GestaoInventory() {
  const location = useLocation();
  const navigate = useNavigate();
  const section = sectionFromPath(location.pathname) ?? "items";
  const activeGroup = sectionGroup(section);

  useEffect(() => {
    if (!sectionFromPath(location.pathname)) navigate(`${inventoryRouteBase}/${sectionSlugs.items}`, { replace: true });
  }, [location.pathname, navigate]);

  const changeSection = (next: Section) => navigate(`${inventoryRouteBase}/${sectionSlugs[next]}`);
  const changeGroup = (next: InventoryGroup) => navigate(`${inventoryRouteBase}/${sectionSlugs[groupSections[next][0]]}`);

  return (
    <AdminGestao
      moduleKey="inventory"
      showSettings={section === "settings"}
      moduleTabs={(
        <div className="space-y-2">
          <AdminPageTabs<InventoryGroup> tabs={inventoryGroups} active={activeGroup} onChange={changeGroup} />
          <AdminPageTabs<Section> tabs={sections.filter((tab) => groupSections[activeGroup].includes(tab.id))} active={section} onChange={changeSection} />
        </div>
      )}
    >
      {section === "foundation" ? <InventoryFoundationPanel /> : section === "preparation" ? <PreparationOperationsPanel /> : section === "portioning" ? <InventoryPortioningPanel /> : section === "portion-stock" ? <InventoryPortionStockPanel /> : section !== "settings" && <InventoryBase section={section} />}
    </AdminGestao>
  );
}

function InventoryBase({ section }: { section: Exclude<Section, "settings" | "foundation" | "documents" | "preparation"> }) {
  const [data, setData] = useState<InventoryOverview>(emptyOverview);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const content = sectionContent[section];

  const load = () => {
    setLoading(true);
    setError("");
    inventoryApi.overview()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar o estoque."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  async function run(action: () => Promise<unknown>, success: string) {
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await action();
      setMessage(success);
      await inventoryApi.overview().then(setData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function refreshAfterAdjustment() {
    setLoading(true);
    setError("");
    try {
      const [overview] = await Promise.all([inventoryApi.overview(), inventoryApi.portionBalances(), inventoryApi.portionReplenishmentAlerts()]);
      setData(overview);
      setMessage("Ajuste registrado. Saldos de insumos e porções atualizados.");
    } catch (err) {
      setError(`Ajuste registrado, mas não foi possível atualizar todas as visões: ${err instanceof Error ? err.message : "tente atualizar novamente."}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-black text-cream">{content.title}</h2>
          <p className="mt-1 text-sm text-stone">{content.description}</p>
        </div>
        <button type="button" onClick={load} className={ghostButtonClass}>
          <RefreshCw size={15} /> Atualizar
        </button>
      </div>

      {loading && (
        <div className="flex min-h-40 items-center justify-center text-stone">
          <Loader2 size={18} className="mr-2 animate-spin" /> Carregando cadastros...
        </div>
      )}

      {!loading && (
        <>
          {section === "items" && <ItemsSection data={data} saving={saving} run={run} />}
          {section === "ingredient-stock" && <IngredientStockSection data={data} saving={saving} onRequestPurchase={() => run(() => inventoryApi.createReplenishmentRequest(), "Solicitação de compras gerada. Nenhum saldo foi alterado.")} onAdjusted={() => void refreshAfterAdjustment()} />}
          {section === "base" && <BaseSection data={data} saving={saving} run={run} />}
          {section === "suppliers" && <SuppliersSection data={data} saving={saving} run={run} />}
          {section === "purchases" && <PurchasesSection data={data} saving={saving} run={run} />}
          {section === "replenishment" && <ReplenishmentSection data={data} saving={saving} onCreatePurchase={() => run(() => inventoryApi.createReplenishmentRequest(), "Solicitação de compras gerada. Nenhum saldo foi alterado.")} />}
          {section === "entries" && <EntriesSection data={data} saving={saving} run={run} />}
        </>
      )}

      {message && <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-200">{message}</p>}
      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-200">{error}</p>}
    </section>
  );
}

function ReplenishmentSection({ data, saving, onCreatePurchase }: { data: InventoryOverview; saving: boolean; onCreatePurchase: () => Promise<void> }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"name" | "current_stock" | "min_stock" | "shortage">("name");
  const needs = useMemo(
    () => data.items
      .filter((item) => item.active && item.item_type !== "finished_good" && item.current_stock !== undefined && item.current_stock < item.min_stock)
      .map((item) => ({ ...item, shortage: Math.max(item.min_stock - (item.current_stock ?? 0), 0) }))
      .sort((a, b) => b.shortage - a.shortage),
    [data.items],
  );
  const visibleNeeds = useMemo(() => filterAndSort(needs, search, sort, { name: (item) => item.name, current_stock: (item) => item.current_stock ?? 0, min_stock: (item) => item.min_stock, shortage: (item) => item.shortage }), [needs, search, sort]);

  const latestCostFor = (itemId: string) => data.purchases
    .flatMap((purchase) => purchase.items)
    .filter((line) => line.item_id === itemId)
    .sort((a, b) => (b.total_cost ?? b.quantity * b.unit_cost) - (a.total_cost ?? a.quantity * a.unit_cost))[0]?.unit_cost ?? 0;

  const estimated = needs.reduce((total, item) => {
    return total + item.shortage * latestCostFor(item.id);
  }, 0);

  const requestPurchase = () => onCreatePurchase();

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-amber-200">Itens abaixo do mínimo</p>
          <p className="mt-1 text-2xl font-black text-amber-100">{needs.length}</p>
        </div>
        <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-stone">Estimativa com último custo</p>
          <p className="mt-1 text-2xl font-black text-cream">{currency(estimated)}</p>
        </div>
      </div>
      <div className="flex flex-col gap-3 rounded-lg border border-gold/25 bg-gold/5 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-black text-cream">Solicitação de compras</p>
          <p className="mt-1 text-xs text-stone">Cria um rascunho com todos os itens abaixo do mínimo. O estoque não é alterado.</p>
        </div>
        <button type="button" disabled={saving || !needs.length} onClick={() => void requestPurchase()} className={buttonClass}>
          {saving ? <Loader2 size={15} className="animate-spin" /> : <ShoppingCart size={15} />} Gerar solicitação
        </button>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "name", label: "Insumo (A-Z)" }, { value: "current_stock", label: "Estoque atual" }, { value: "min_stock", label: "Mínimo" }, { value: "shortage", label: "Necessidade" }]} />
        <TableHeader columns={["Insumo", "Estoque atual", "Mínimo", "Necessidade", "Unidade"]} />
        {visibleNeeds.map((item) => (
          <div key={item.id} className="grid grid-cols-[1.5fr_1fr_1fr_1fr_.8fr] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.name}<small className="block text-stone">{item.sku || item.category_name || "Sem categoria"}</small></span>
            <span className="text-red-200">{quantity(item.current_stock)}</span>
            <span className="text-stone">{quantity(item.min_stock)}</span>
            <span className="font-bold text-amber-200">{quantity(item.shortage)}</span>
            <span className="text-stone">{item.unit_symbol || item.unit_name || "-"}</span>
          </div>
        ))}
        {!visibleNeeds.length && <EmptyRow text={needs.length ? "Nenhum insumo encontrado." : "Nenhum item abaixo do estoque mínimo."} />}
      </div>
      <p className="text-xs text-stone">A necessidade é calculada a partir do estoque atual e do mínimo cadastrado. O custo unitário usa o último custo disponível; quando ausente, fica em R$ 0,00 para revisão na aba Compras.</p>
    </div>
  );
}

function IngredientStockSection({ data, saving, onRequestPurchase, onAdjusted }: { data: InventoryOverview; saving: boolean; onRequestPurchase: () => Promise<void>; onAdjusted: () => void }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"name" | "current_stock" | "min_stock">("name");
  const [adjusting, setAdjusting] = useState<AdjustmentItem | null>(null);
  const ingredients = data.items
    .filter((item) => item.active && item.item_type === "ingredient")
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
  const visibleIngredients = useMemo(() => filterAndSort(ingredients, search, sort, { name: (item) => item.name, current_stock: (item) => item.current_stock ?? 0, min_stock: (item) => item.min_stock }), [ingredients, search, sort]);

  return (
    <div className="overflow-hidden rounded-lg border border-surface-03">
      <div className="flex flex-col gap-3 bg-surface-01 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-black text-cream">Estoque de Insumos</h2>
          <p className="mt-1 text-sm text-stone">Saldo atual dos insumos cadastrados. Entradas e saídas são registradas na aba Entradas.</p>
        </div>
        <button type="button" disabled={saving || !ingredients.some((item) => (item.current_stock ?? 0) < item.min_stock)} onClick={() => void onRequestPurchase()} className={buttonClass}>
          {saving ? <Loader2 size={15} className="animate-spin" /> : <ShoppingCart size={15} />} Solicitar compra
        </button>
      </div>
      <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "name", label: "Insumo (A-Z)" }, { value: "current_stock", label: "Saldo atual" }, { value: "min_stock", label: "Mínimo" }]} />
      <div className="overflow-x-auto"><div className="min-w-[900px]">
      <TableHeader columns={["Insumo", "Unidade", "Local", "Saldo atual", "Mínimo", "Situação", "Ação"]} />
      {visibleIngredients.map((item) => {
        const current = item.current_stock ?? 0;
        const belowMinimum = current < item.min_stock;
        return (
          <div key={item.id} className="grid grid-cols-7 items-center gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.name}<small className="block text-stone">{item.sku || "Sem SKU"}</small></span>
            <span className="text-stone">{item.unit_symbol || item.unit_name || "-"}</span>
            <span className="text-stone">{item.default_location_name || "-"}</span>
            <span className={belowMinimum ? "font-bold text-amber-200" : "text-emerald-200"}>{quantity(current)}</span>
            <span className="text-stone">{quantity(item.min_stock)}</span>
            <span className={belowMinimum ? "font-bold text-amber-200" : "text-emerald-200"}>{belowMinimum ? "Abaixo do mínimo" : "Disponível"}</span>
            <button type="button" className="rounded-lg border border-surface-03 px-2 py-2 text-xs font-bold text-cream hover:bg-surface-03 disabled:opacity-50" disabled={saving} onClick={() => setAdjusting({ id: item.id, name: item.name, unitSymbol: item.unit_symbol || item.unit_name || "unid." })}>Corrigir / registrar perda{hasUnresolvedAdjustment(item.id) && <small className="block text-amber-300">Resultado pendente</small>}</button>
          </div>
        );
      })}
      {!visibleIngredients.length && <EmptyRow text={ingredients.length ? "Nenhum insumo encontrado." : "Nenhum insumo ativo cadastrado."} />}
      </div></div>
      <InventoryStockAdjustmentDialog item={adjusting} onClose={() => setAdjusting(null)} onAdjusted={onAdjusted} />
    </div>
  );
}

function ItemsSection({
  data,
  saving,
  run,
}: {
  data: InventoryOverview;
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"name" | "current_stock" | "min_stock">("name");
  const [form, setForm] = useState({
    name: "",
    item_type: "ingredient" as InventoryItem["item_type"],
    portionable: false,
    category_id: "",
    unit_id: "",
    weight_quantity: null as number | null,
    weight_unit_id: "",
    default_location_id: "",
    min_stock: 0,
    notes: "",
    active: true,
  });
  const [editing, setEditing] = useState<InventoryItem | null>(null);
  const navigate = useNavigate();
  const selectedUnit = data.units.find((item) => item.id === form.unit_id);
  const weightUnits = data.units.filter((item) => item.active && item.dimension === "mass" && item.conversion_factor != null);
  const selectedUnitUnclassified = Boolean(selectedUnit && !selectedUnit.dimension);
  const showPackageWeight = Boolean(selectedUnit && (selectedUnit.has_weight || selectedUnit.dimension === "count" || !selectedUnit.dimension || selectedUnit.unit_type === "package"));

  const save = () => run(
    () => (editing ? inventoryApi.updateItem(editing.id, {
      ...form,
      category_id: form.category_id || null,
      unit_id: form.unit_id || null,
      weight_quantity: form.weight_quantity,
      weight_unit_id: form.weight_unit_id || null,
      default_location_id: form.default_location_id || null,
      notes: form.notes || null,
    }) : inventoryApi.createItem({
      ...form,
      category_id: form.category_id || null,
      unit_id: form.unit_id || null,
      weight_quantity: form.weight_quantity,
      weight_unit_id: form.weight_unit_id || null,
      default_location_id: form.default_location_id || null,
      notes: form.notes || null,
    })), editing ? "Item de estoque atualizado." : "Item de estoque cadastrado.",
  ).then(() => { setEditing(null); setForm({ ...form, name: "", notes: "", weight_quantity: null, weight_unit_id: "" }); });

  const editItem = (item: InventoryItem) => { setEditing(item); setForm({ name: item.name, item_type: item.item_type, portionable: item.portionable, category_id: item.category_id || "", unit_id: item.unit_id || "", weight_quantity: item.weight_quantity ?? null, weight_unit_id: item.weight_unit_id || "", default_location_id: item.default_location_id || "", min_stock: item.min_stock, notes: item.notes || "", active: item.active }); };
  const visibleItems = useMemo(() => filterAndSort(data.items, search, sort, { name: (item) => item.name, current_stock: (item) => item.current_stock ?? 0, min_stock: (item) => item.min_stock }), [data.items, search, sort]);

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">{editing ? "Editar insumo" : "Novo insumo"}</h3>
        {editing && <button type="button" className={ghostButtonClass} onClick={() => { setEditing(null); setForm({ ...form, name: "", notes: "" }); }}>Cancelar edição</button>}
        <div className="mt-4 space-y-3">
          <label className="block text-sm text-stone">Identificação do insumo<input className={inputClass} placeholder="Ex.: Calabresa" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <p className="rounded-md border border-dashed border-surface-03 px-3 py-2 text-xs text-stone">{form.item_type === "ingredient" ? "O SKU será gerado automaticamente ao cadastrar o insumo." : "O SKU automático é aplicado aos insumos; este tipo de item pode usar SKU integrado, se necessário."}</p>
          <label className="block text-sm text-stone">Tipo de cadastro<select className={inputClass} value={form.item_type} onChange={(e) => setForm({ ...form, item_type: e.target.value as InventoryItem["item_type"] })}>
            <option value="ingredient">Insumo</option>
            <option value="finished_good">Produto acabado</option>
            <option value="packaging">Embalagem</option>
            <option value="supply">Material</option>
          </select></label>
          <label className="block text-sm text-stone">Produto será porcionado para uso?
            <select className={inputClass} value={form.portionable ? "yes" : "no"} onChange={(e) => setForm({ ...form, portionable: e.target.value === "yes" })}>
              <option value="no">Não será porcionado para uso</option>
              <option value="yes">Será porcionado para uso</option>
            </select>
          </label>
          <label className="block text-sm text-stone">Categoria<select className={inputClass} value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">Selecione a categoria</option>
            {data.categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label className="block text-sm text-stone">Unidade de compra / estoque<select className={inputClass} value={form.unit_id} onChange={(e) => setForm({ ...form, unit_id: e.target.value, weight_quantity: null, weight_unit_id: "" })}>
            <option value="">Selecione a unidade</option>
            {data.units.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name} ({item.symbol}){!item.dimension ? " — classificação pendente" : ""}</option>)}
          </select></label>
          {selectedUnitUnclassified && <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"><AlertTriangle size={15} className="mt-0.5 shrink-0" /><span>Esta unidade ainda não tem classificação técnica. Classifique-a em Base do Estoque antes de solicitar o porcionamento. <button type="button" className="font-bold underline" onClick={() => navigate(`${inventoryRouteBase}/${sectionSlugs.base}`)}>Abrir Base / Classificação</button></span></div>}
          {showPackageWeight && <div className="rounded-md border border-gold/40 bg-gold/10 p-3 text-sm text-stone"><p className="font-bold text-cream">Peso por unidade/embalagem</p><p className="mt-1 text-xs">Informe para porção, pacote, pote, balde ou caixa. Para KG ou GR classificados como massa, a conversão é direta e este campo não é necessário.</p><div className="mt-2 grid gap-2 sm:grid-cols-2"><label>Peso total por unidade<input className={inputClass} required={Boolean(selectedUnit?.has_weight)} type="number" min="0.000001" step="0.000001" placeholder="Ex.: 5" value={form.weight_quantity ?? ""} onChange={(e) => setForm({ ...form, weight_quantity: e.target.value ? Number(e.target.value) : null })} /></label><label>Unidade do peso
            <select className={inputClass} required={Boolean(selectedUnit?.has_weight)} value={form.weight_unit_id} onChange={(e) => setForm({ ...form, weight_unit_id: e.target.value })}>
              <option value="">Selecione a unidade do peso</option>
              {weightUnits.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.symbol})</option>)}
            </select></label></div></div>}
          <label className="block text-sm text-stone">Local padrão<select className={inputClass} value={form.default_location_id} onChange={(e) => setForm({ ...form, default_location_id: e.target.value })}>
            <option value="">Selecione o local</option>
            {data.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label className="block text-sm text-stone">Estoque mínimo<input className={inputClass} type="number" min="0" step="0.001" placeholder="Ex.: 5" value={form.min_stock} onChange={(e) => setForm({ ...form, min_stock: Number(e.target.value) })} /></label>
          <textarea className={inputClass} placeholder="Observações internas" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving || !form.name} onClick={save} className={buttonClass}>
            <Plus size={15} /> Cadastrar item
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-surface-03">
        <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "name", label: "Item (A-Z)" }, { value: "current_stock", label: "Saldo" }, { value: "min_stock", label: "Mínimo" }]} />
        <TableHeader columns={["Item", "Tipo", "Unidade", "Categoria", "Saldo", "Minimo", ""]} />
        {visibleItems.map((item) => (
          <div key={item.id} className="grid grid-cols-[1.5fr_1fr_1fr_1fr_1fr_.7fr_auto] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.name}<small className="block text-stone">{item.sku || "-"}</small></span>
            <span className="text-stone">{item.item_type.replace(/_/g, " ")}</span>
            <span className="text-stone">{item.unit_symbol || "-"}{item.weight_quantity != null && item.weight_unit_symbol ? <small className="block text-gold">{quantity(item.weight_quantity)} {item.weight_unit_symbol}/unidade</small> : null}</span>
            <span className="text-stone">{item.category_name || "-"}</span>
            <span className={(item.current_stock ?? 0) <= item.min_stock ? "font-bold text-amber-300" : "text-stone"}>{quantity(item.current_stock)}</span>
            <span className="text-stone">{quantity(item.min_stock)}</span>
            <div className="flex gap-1"><button type="button" className="rounded-lg p-2 text-stone hover:text-cream" disabled={saving} onClick={() => editItem(item)} title="Editar"><Pencil size={15} /></button><DeleteButton disabled={saving} onClick={() => run(() => inventoryApi.removeItem(item.id), "Item removido.")} /></div>
          </div>
        ))}
        {!visibleItems.length && <EmptyRow text={data.items.length ? "Nenhum item encontrado." : "Nenhum item cadastrado."} />}
      </div>
    </div>
  );
}

function BaseSection({
  data,
  saving,
  run,
}: {
  data: InventoryOverview;
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <UnitsPanel units={data.units} saving={saving} run={run} />
      <SimplePanel
        title="Categorias"
        placeholder="Ex: Laticinios"
        rows={data.categories}
        create={(name) => inventoryApi.createCategory({ name, description: null, active: true })}
        update={(id, name) => inventoryApi.updateCategory(id, { name, description: null, active: true })}
        remove={(id) => inventoryApi.removeCategory(id)}
        saving={saving}
        run={run}
      />
      <SimplePanel
        title="Locais"
        placeholder="Ex: Camara fria"
        rows={data.locations}
        create={(name) => inventoryApi.createLocation({ name, description: null, active: true })}
        update={(id, name) => inventoryApi.updateLocation(id, { name, description: null, active: true })}
        remove={(id) => inventoryApi.removeLocation(id)}
        saving={saving}
        run={run}
      />
      <InventoryUnitClassificationPanel />
    </div>
  );
}

function UnitsPanel({
  units,
  saving,
  run,
}: {
  units: InventoryUnit[];
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [form, setForm] = useState({ name: "", symbol: "", unit_type: "unit" as InventoryUnit["unit_type"], has_weight: false });
  const [editing, setEditing] = useState<InventoryUnit | null>(null);
  const [search, setSearch] = useState("");
  const save = () => run(
    () => editing ? inventoryApi.updateUnit(editing.id, { ...form, active: editing.active }) : inventoryApi.createUnit({ ...form, active: true }),
    editing ? "Unidade atualizada." : "Unidade cadastrada.",
  ).then(() => { setEditing(null); setForm({ name: "", symbol: "", unit_type: "unit", has_weight: false }); });

  return (
    <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
      <h3 className="text-sm font-black uppercase tracking-wide text-parchment">{editing ? "Editar unidade" : "Unidades"}</h3>
      {editing && <button type="button" className={ghostButtonClass} onClick={() => { setEditing(null); setForm({ name: "", symbol: "", unit_type: "unit", has_weight: false }); }}>Cancelar edição</button>}
      <div className="mt-4 space-y-3">
        <input className={inputClass} placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className={inputClass} placeholder="Sigla, ex: kg" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} />
        <select className={inputClass} value={form.unit_type} onChange={(e) => setForm({ ...form, unit_type: e.target.value as InventoryUnit["unit_type"] })}>
          <option value="unit">Unidade / contagem</option>
          <option value="mass">Massa</option>
          <option value="volume">Volume</option>
          <option value="package">Embalagem (pacote, pote, balde ou caixa)</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-stone"><input type="checkbox" checked={form.has_weight} onChange={(e) => setForm({ ...form, has_weight: e.target.checked })} /> Esta unidade de compra tem peso próprio (pacote, pote, balde ou caixa)</label>
        <button type="button" disabled={saving || !form.name || !form.symbol} onClick={save} className={buttonClass}><Plus size={15} /> {editing ? "Salvar alteração" : "Adicionar unidade"}</button>
      </div>
      <input className={`${inputClass} mt-4`} placeholder="Buscar unidade..." value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Buscar unidade" />
      <ListRows rows={units.filter((item) => `${item.name} ${item.symbol}`.toLocaleLowerCase("pt-BR").includes(search.trim().toLocaleLowerCase("pt-BR"))).sort((a, b) => a.name.localeCompare(b.name, "pt-BR")).map((item) => ({ id: item.id, name: `${item.name} (${item.symbol})`, edit: () => { setEditing(item); setForm({ name: item.name, symbol: item.symbol, unit_type: item.unit_type, has_weight: item.has_weight }); } }))} saving={saving} remove={(id) => run(() => inventoryApi.removeUnit(id), "Unidade removida.")} />
    </div>
  );
}

function SimplePanel<T extends { id: string; name: string }>({
  title,
  placeholder,
  rows,
  create,
  remove,
  update,
  saving,
  run,
}: {
  title: string;
  placeholder: string;
  rows: T[];
  create: (name: string) => Promise<unknown>;
  remove: (id: string) => Promise<unknown>;
  update?: (id: string, name: string) => Promise<unknown>;
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const save = () => run(() => editingId && update ? update(editingId, name) : create(name), `${title} atualizado.`).then(() => { setName(""); setEditingId(null); });
  return (
    <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
      <h3 className="text-sm font-black uppercase tracking-wide text-parchment">{title}</h3>
        <div className="mt-4 flex gap-2">
        <input className={inputClass} placeholder={placeholder} value={name} onChange={(e) => setName(e.target.value)} />
        <button type="button" aria-label={editingId ? `Salvar ${title.toLowerCase()}` : `Adicionar ${title.toLowerCase()}`} disabled={saving || !name} onClick={save} className={buttonClass}><Plus size={15} /> <span className="hidden sm:inline">{editingId ? "Salvar" : "Adicionar"}</span></button>
      </div>
      <input className={`${inputClass} mt-3`} placeholder={`Buscar ${title.toLowerCase()}...`} value={search} onChange={(event) => setSearch(event.target.value)} aria-label={`Buscar ${title.toLowerCase()}`} />
      <ListRows rows={rows.filter((row) => row.name.toLocaleLowerCase("pt-BR").includes(search.trim().toLocaleLowerCase("pt-BR"))).sort((a, b) => a.name.localeCompare(b.name, "pt-BR")).map((row) => ({ ...row, edit: update ? () => { setEditingId(row.id); setName(row.name); } : undefined }))} saving={saving} remove={(id) => run(() => remove(id), `${title} removido.`)} />
    </div>
  );
}

function SuppliersSection({
  data,
  saving,
  run,
}: {
  data: InventoryOverview;
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"name" | "document">("name");
  const [form, setForm] = useState({ name: "", document: "", phone: "", email: "", notes: "" });
  const [editing, setEditing] = useState<InventorySupplier | null>(null);
  const save = () => run(
    () => editing ? inventoryApi.updateSupplier(editing.id, { ...form, active: editing.active }) : inventoryApi.createSupplier({ ...form, active: true }),
    editing ? "Fornecedor atualizado." : "Fornecedor cadastrado.",
  ).then(() => { setEditing(null); setForm({ name: "", document: "", phone: "", email: "", notes: "" }); });
  const visibleSuppliers = useMemo(() => filterAndSort(data.suppliers, search, sort, { name: (item) => item.name, document: (item) => item.document || "" }), [data.suppliers, search, sort]);

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">{editing ? "Editar fornecedor" : "Novo fornecedor"}</h3>
        {editing && <button type="button" className={ghostButtonClass} onClick={() => { setEditing(null); setForm({ name: "", document: "", phone: "", email: "", notes: "" }); }}>Cancelar edição</button>}
        <div className="mt-4 space-y-3">
          <input className={inputClass} placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className={inputClass} placeholder="Documento" value={form.document} onChange={(e) => setForm({ ...form, document: e.target.value })} />
          <input className={inputClass} placeholder="Telefone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <input className={inputClass} placeholder="E-mail" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <textarea className={inputClass} placeholder="Observações" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving || !form.name} onClick={save} className={buttonClass}><Plus size={15} /> Cadastrar</button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "name", label: "Fornecedor (A-Z)" }, { value: "document", label: "Documento" }]} />
        <TableHeader columns={["Fornecedor", "Contato", "Documento", ""]} />
        {visibleSuppliers.map((item) => (
          <div key={item.id} className="grid grid-cols-[1.4fr_1.3fr_1fr_auto] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.name}</span>
            <span className="text-stone">{item.phone || item.email || "-"}</span>
            <span className="text-stone">{item.document || "-"}</span>
            <div className="flex gap-1"><button type="button" className="rounded-lg p-2 text-stone hover:text-cream" disabled={saving} onClick={() => { setEditing(item); setForm({ name: item.name, document: item.document || "", phone: item.phone || "", email: item.email || "", notes: item.notes || "" }); }} title="Editar"><Pencil size={15} /></button><DeleteButton disabled={saving} onClick={() => run(() => inventoryApi.removeSupplier(item.id), "Fornecedor removido.")} /></div>
          </div>
        ))}
        {!visibleSuppliers.length && <EmptyRow text={data.suppliers.length ? "Nenhum fornecedor encontrado." : "Nenhum fornecedor cadastrado."} />}
      </div>
    </div>
  );
}

function PurchasesSection({
  data,
  saving,
  run,
}: {
  data: InventoryOverview;
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"reference" | "total_amount">("reference");
  const [form, setForm] = useState({
    supplier_id: "",
    invoice_number: "",
    expected_date: "",
    notes: "",
    item_id: "",
    quantity: 1,
    unit_cost: 0,
  });

  const total = useMemo(() => form.quantity * form.unit_cost, [form.quantity, form.unit_cost]);
  const save = () => {
    const items: InventoryPurchaseItem[] = form.item_id
      ? [{ item_id: form.item_id, quantity: form.quantity, unit_cost: form.unit_cost }]
      : [];
    return run(
      () => inventoryApi.createPurchase({
        supplier_id: form.supplier_id || null,
        status: "draft",
        invoice_number: form.invoice_number || null,
        expected_date: form.expected_date || null,
        notes: form.notes || null,
        items,
      }),
      "Compra em rascunho cadastrada. Nenhum saldo foi alterado.",
    ).then(() => setForm({ supplier_id: "", invoice_number: "", expected_date: "", notes: "", item_id: "", quantity: 1, unit_cost: 0 }));
  };

  const confirmPurchase = (purchase: InventoryPurchase) => run(
    () => inventoryApi.updatePurchase(purchase.id, {
      supplier_id: purchase.supplier_id || null,
      status: "confirmed",
      invoice_number: purchase.invoice_number || null,
      expected_date: purchase.expected_date || null,
      notes: purchase.notes || null,
      items: purchase.items.map((item) => ({
        item_id: item.item_id,
        quantity: item.quantity,
        unit_cost: item.unit_cost,
      })),
    }),
    "Compra confirmada. O Financeiro criara a conta a pagar se a automacao estiver habilitada.",
  );
  const visiblePurchases = useMemo(() => filterAndSort(data.purchases, search, sort, { reference: (item) => `${item.invoice_number || ""} ${item.supplier_name || ""} ${item.id}`, total_amount: (item) => item.total_amount ?? 0 }), [data.purchases, search, sort]);

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Nova compra em rascunho</h3>
        <div className="mt-4 space-y-3">
          <label className="block text-sm text-stone">Fornecedor<select className={inputClass} value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}>
            <option value="">Selecione o fornecedor</option>
            {data.suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label className="block text-sm text-stone">Número da nota ou pedido<input className={inputClass} placeholder="Ex.: NF 12345" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></label>
          <label className="block text-sm text-stone">Data prevista de recebimento<input className={inputClass} type="date" value={form.expected_date} onChange={(e) => setForm({ ...form, expected_date: e.target.value })} /></label>
          <label className="block text-sm text-stone">Insumo<select className={inputClass} value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })}>
            <option value="">Selecione o insumo</option>
            {data.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-sm text-stone">Quantidade<input aria-label="Quantidade da compra" className={inputClass} type="number" min="0.001" step="0.001" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} /></label>
            <label className="block text-sm text-stone">Custo unitário (R$)<input aria-label="Custo unitário da compra" className={inputClass} type="number" min="0" step="0.01" value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: Number(e.target.value) })} /></label>
          </div>
          <p className="text-sm font-bold text-stone">Total: {currency(total)}</p>
          <textarea className={inputClass} placeholder="Observações" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving} onClick={save} className={buttonClass}><Plus size={15} /> Salvar rascunho</button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "reference", label: "Compra (A-Z)" }, { value: "total_amount", label: "Valor total" }]} />
        <TableHeader columns={["Compra", "Fornecedor", "Itens", "Total", ""]} />
        {visiblePurchases.map((item) => (
          <div key={item.id} className="grid grid-cols-[1fr_1fr_1.2fr_.8fr_auto] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.invoice_number || item.id}<small className="block text-stone">{item.status === "confirmed" ? "Confirmada" : "Rascunho"}</small></span>
            <span className="text-stone">{item.supplier_name || "-"}</span>
            <span className="text-stone">{item.items.map((row) => row.item_name || row.item_id).join(", ") || "-"}</span>
            <span className="text-stone">{currency(item.total_amount)}</span>
            <span className="flex items-center gap-2">
              {item.status !== "confirmed" && (
                <button type="button" disabled={saving} onClick={() => confirmPurchase(item)} className="rounded-lg border border-emerald-500/30 p-2 text-emerald-300 transition hover:bg-emerald-500/10" title="Confirmar compra">
                  <CheckCircle2 size={16} />
                </button>
              )}
              {item.status !== "confirmed" && (
                <DeleteButton disabled={saving} onClick={() => run(() => inventoryApi.removePurchase(item.id), "Compra removida.")} />
              )}
            </span>
          </div>
        ))}
        {!visiblePurchases.length && <EmptyRow text={data.purchases.length ? "Nenhuma compra encontrada." : "Nenhuma compra cadastrada."} />}
      </div>
    </div>
  );
}

function EntriesSection({
  data,
  saving,
  run,
}: {
  data: InventoryOverview;
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"item" | "quantity" | "cost">("item");
  const [form, setForm] = useState({ item_id: "", location_id: "", movement_type: "in" as "in" | "out", quantity: 1, unit_cost: 0, reason: "initial_stock", notes: "" });
  const save = () => run(
    () => inventoryApi.createManualEntry({
      item_id: form.item_id,
      location_id: form.location_id || null,
      movement_type: form.movement_type,
      quantity: form.quantity,
      unit_cost: form.unit_cost,
      reason: form.reason,
      notes: form.notes || null,
    }),
    "Movimento manual registrado.",
  ).then(() => setForm({ item_id: "", location_id: "", movement_type: "in", quantity: 1, unit_cost: 0, reason: "initial_stock", notes: "" }));
  const visibleEntries = useMemo(() => filterAndSort(data.manual_entries, search, sort, { item: (entry) => `${entry.item_name || ""} ${entry.movement_type || ""} ${entry.location_name || ""}`, quantity: (entry) => entry.quantity, cost: (entry) => entry.unit_cost }), [data.manual_entries, search, sort]);

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Novo movimento manual</h3>
        <div className="mt-4 space-y-3">
          <label className="block text-xs font-bold text-stone">Tipo de movimento<select className={`${inputClass} mt-1`} value={form.movement_type} onChange={(e) => setForm({ ...form, movement_type: e.target.value as "in" | "out", reason: e.target.value === "out" ? "manual_out" : "initial_stock" })}>
            <option value="in">Entrada de estoque</option>
            <option value="out">Saída de estoque</option>
          </select></label>
          <label className="block text-xs font-bold text-stone">Insumo<select className={`${inputClass} mt-1`} value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })}>
            <option value="">Selecione o insumo</option>
            {data.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <label className="block text-xs font-bold text-stone">Local de estoque<select className={`${inputClass} mt-1`} value={form.location_id} onChange={(e) => setForm({ ...form, location_id: e.target.value })}>
            <option value="">Selecione o local</option>
            {data.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select></label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-xs font-bold text-stone">Quantidade{data.items.find((item) => item.id === form.item_id)?.unit_symbol ? ` (${data.items.find((item) => item.id === form.item_id)?.unit_symbol})` : ""}<input className={`${inputClass} mt-1`} type="number" min="0.001" step="0.001" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} /></label>
            <label className="block text-xs font-bold text-stone">Custo unitário (R$)<input className={`${inputClass} mt-1`} type="number" min="0" step="0.01" value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: Number(e.target.value) })} /></label>
          </div>
          <label className="block text-xs font-bold text-stone">Motivo do movimento<input className={`${inputClass} mt-1`} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></label>
          <label className="block text-xs font-bold text-stone">Observações<textarea className={`${inputClass} mt-1`} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
          <button type="button" disabled={saving || !form.item_id} onClick={save} className={buttonClass}><Plus size={15} /> Registrar movimento</button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "item", label: "Item (A-Z)" }, { value: "quantity", label: "Quantidade" }, { value: "cost", label: "Custo unitário" }]} />
        <TableHeader columns={["Item", "Tipo", "Local", "Quantidade", "Custo", ""]} />
        {visibleEntries.map((item) => (
          <div key={item.id} className="grid grid-cols-[1.2fr_.8fr_1fr_.8fr_.8fr_auto] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.item_name || item.item_id}</span>
            <span className={item.movement_type === "out" ? "font-bold text-red-300" : "font-bold text-emerald-300"}>{item.movement_type === "out" ? "Saida" : "Entrada"}</span>
            <span className="text-stone">{item.location_name || "-"}</span>
           <span className="text-stone">{quantity(item.quantity)}</span>
            <span className="text-stone">{currency(item.unit_cost)}</span>
            {item.reversed ? <span className="text-stone">Estornada</span> : <button type="button" disabled={saving} onClick={() => run(() => inventoryApi.removeManualEntry(item.id), "Entrada estornada; historico preservado.")} className={ghostButtonClass}>Estornar</button>}
          </div>
        ))}
        {!visibleEntries.length && <EmptyRow text={data.manual_entries.length ? "Nenhum movimento encontrado." : "Nenhuma entrada manual registrada."} />}
      </div>
      <div className="xl:col-span-2 border-t border-surface-03 pt-5">
        <InventoryReceiptDocumentsPanel />
      </div>
    </div>
  );
}

function TableHeader({ columns }: { columns: string[] }) {
  return (
    <div className="grid gap-3 bg-surface-03/70 px-4 py-3 text-xs font-black uppercase tracking-wide text-stone" style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` }}>
      {columns.map((column) => <span key={column}>{column}</span>)}
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <div className="border-t border-surface-03 bg-surface-01 px-4 py-8 text-center text-sm text-stone">{text}</div>;
}

function DeleteButton({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className="rounded-lg p-2 text-stone transition hover:bg-red-500/10 hover:text-red-300 disabled:opacity-50" title="Remover">
      <Trash2 size={15} />
    </button>
  );
}

function ListRows({
  rows,
  saving,
  remove,
}: {
  rows: Array<{ id: string; name: string; edit?: () => void }>;
  saving: boolean;
  remove: (id: string) => void;
}) {
  return (
    <div className="mt-4 space-y-2">
      {rows.map((row) => (
        <div key={row.id} className="flex items-center justify-between gap-3 rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-sm">
          <span className="font-semibold text-cream">{row.name}</span>
          <div className="flex gap-1">{row.edit && <button type="button" className="rounded-lg p-2 text-stone hover:text-cream" disabled={saving} onClick={row.edit} title="Editar"><Pencil size={15} /></button>}<DeleteButton disabled={saving} onClick={() => remove(row.id)} /></div>
        </div>
      ))}
      {!rows.length && <p className="rounded-lg border border-surface-03 bg-surface-02 px-3 py-4 text-center text-sm text-stone">Sem registros.</p>}
    </div>
  );
}
