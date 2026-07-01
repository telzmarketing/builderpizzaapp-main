import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Database, Layers3, Loader2, Package, Plus, RefreshCw, Settings, ShoppingCart, Trash2, Truck } from "lucide-react";
import { AdminPageTabs, type AdminPageTab } from "@/components/admin/AdminPageChrome";
import AdminGestao from "./AdminGestao";
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

type Section = "settings" | "items" | "base" | "suppliers" | "purchases" | "entries";

const sections: AdminPageTab<Section>[] = [
  { id: "settings", label: "Configuracoes", icon: Settings },
  { id: "items", label: "Insumos", icon: Package },
  { id: "base", label: "Base", icon: Layers3 },
  { id: "suppliers", label: "Fornecedores", icon: Truck },
  { id: "purchases", label: "Compras", icon: ShoppingCart },
  { id: "entries", label: "Entradas", icon: Database },
];

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

export default function GestaoInventory() {
  const [section, setSection] = useState<Section>("settings");

  return (
    <AdminGestao
      moduleKey="inventory"
      showSettings={section === "settings"}
      moduleTabs={<AdminPageTabs<Section> tabs={sections} active={section} onChange={setSection} />}
    >
      {section !== "settings" && <InventoryBase section={section} />}
    </AdminGestao>
  );
}

function InventoryBase({ section }: { section: Exclude<Section, "settings"> }) {
  const [data, setData] = useState<InventoryOverview>(emptyOverview);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

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

  return (
    <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-black text-cream">Cadastros base de Estoque</h2>
          <p className="mt-1 text-sm text-stone">
            Insumos, unidades, categorias, locais, fornecedores, compras em rascunho e entradas manuais.
          </p>
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
          {section === "base" && <BaseSection data={data} saving={saving} run={run} />}
          {section === "suppliers" && <SuppliersSection data={data} saving={saving} run={run} />}
          {section === "purchases" && <PurchasesSection data={data} saving={saving} run={run} />}
          {section === "entries" && <EntriesSection data={data} saving={saving} run={run} />}
        </>
      )}

      {message && <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-200">{message}</p>}
      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-200">{error}</p>}
    </section>
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
  const [form, setForm] = useState({
    name: "",
    sku: "",
    item_type: "ingredient" as InventoryItem["item_type"],
    category_id: "",
    unit_id: "",
    default_location_id: "",
    min_stock: 0,
    notes: "",
    active: true,
  });

  const save = () => run(
    () => inventoryApi.createItem({
      ...form,
      sku: form.sku || null,
      category_id: form.category_id || null,
      unit_id: form.unit_id || null,
      default_location_id: form.default_location_id || null,
      notes: form.notes || null,
    }),
    "Item de estoque cadastrado.",
  ).then(() => setForm({ ...form, name: "", sku: "", notes: "" }));

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Novo item</h3>
        <div className="mt-4 space-y-3">
          <input className={inputClass} placeholder="Nome do insumo ou produto de estoque" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className={inputClass} placeholder="SKU interno" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />
          <select className={inputClass} value={form.item_type} onChange={(e) => setForm({ ...form, item_type: e.target.value as InventoryItem["item_type"] })}>
            <option value="ingredient">Insumo</option>
            <option value="finished_good">Produto acabado</option>
            <option value="packaging">Embalagem</option>
            <option value="supply">Material</option>
          </select>
          <select className={inputClass} value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">Categoria</option>
            {data.categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select className={inputClass} value={form.unit_id} onChange={(e) => setForm({ ...form, unit_id: e.target.value })}>
            <option value="">Unidade base</option>
            {data.units.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.symbol})</option>)}
          </select>
          <select className={inputClass} value={form.default_location_id} onChange={(e) => setForm({ ...form, default_location_id: e.target.value })}>
            <option value="">Local padrao</option>
            {data.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <input className={inputClass} type="number" min="0" step="0.001" placeholder="Estoque minimo" value={form.min_stock} onChange={(e) => setForm({ ...form, min_stock: Number(e.target.value) })} />
          <textarea className={inputClass} placeholder="Observacoes internas" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving || !form.name} onClick={save} className={buttonClass}>
            <Plus size={15} /> Cadastrar item
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-surface-03">
        <TableHeader columns={["Item", "Tipo", "Unidade", "Categoria", "Saldo", "Minimo", ""]} />
        {data.items.map((item) => (
          <div key={item.id} className="grid grid-cols-[1.5fr_1fr_1fr_1fr_1fr_.7fr_auto] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.name}<small className="block text-stone">{item.sku || "-"}</small></span>
            <span className="text-stone">{item.item_type.replace(/_/g, " ")}</span>
            <span className="text-stone">{item.unit_symbol || "-"}</span>
            <span className="text-stone">{item.category_name || "-"}</span>
            <span className={(item.current_stock ?? 0) <= item.min_stock ? "font-bold text-amber-300" : "text-stone"}>{item.current_stock ?? 0}</span>
            <span className="text-stone">{item.min_stock}</span>
            <DeleteButton disabled={saving} onClick={() => run(() => inventoryApi.removeItem(item.id), "Item removido.")} />
          </div>
        ))}
        {!data.items.length && <EmptyRow text="Nenhum item cadastrado." />}
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
        remove={(id) => inventoryApi.removeCategory(id)}
        saving={saving}
        run={run}
      />
      <SimplePanel
        title="Locais"
        placeholder="Ex: Camara fria"
        rows={data.locations}
        create={(name) => inventoryApi.createLocation({ name, description: null, active: true })}
        remove={(id) => inventoryApi.removeLocation(id)}
        saving={saving}
        run={run}
      />
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
  const [form, setForm] = useState({ name: "", symbol: "", unit_type: "unit" as InventoryUnit["unit_type"] });
  const save = () => run(
    () => inventoryApi.createUnit({ ...form, active: true }),
    "Unidade cadastrada.",
  ).then(() => setForm({ name: "", symbol: "", unit_type: "unit" }));

  return (
    <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
      <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Unidades</h3>
      <div className="mt-4 space-y-3">
        <input className={inputClass} placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className={inputClass} placeholder="Sigla, ex: kg" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} />
        <select className={inputClass} value={form.unit_type} onChange={(e) => setForm({ ...form, unit_type: e.target.value as InventoryUnit["unit_type"] })}>
          <option value="unit">Unidade</option>
          <option value="mass">Massa</option>
          <option value="volume">Volume</option>
          <option value="package">Pacote</option>
        </select>
        <button type="button" disabled={saving || !form.name || !form.symbol} onClick={save} className={buttonClass}><Plus size={15} /> Adicionar</button>
      </div>
      <ListRows rows={units.map((item) => ({ id: item.id, name: `${item.name} (${item.symbol})` }))} saving={saving} remove={(id) => run(() => inventoryApi.removeUnit(id), "Unidade removida.")} />
    </div>
  );
}

function SimplePanel<T extends { id: string; name: string }>({
  title,
  placeholder,
  rows,
  create,
  remove,
  saving,
  run,
}: {
  title: string;
  placeholder: string;
  rows: T[];
  create: (name: string) => Promise<unknown>;
  remove: (id: string) => Promise<unknown>;
  saving: boolean;
  run: (action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const save = () => run(() => create(name), `${title} atualizado.`).then(() => setName(""));
  return (
    <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
      <h3 className="text-sm font-black uppercase tracking-wide text-parchment">{title}</h3>
      <div className="mt-4 flex gap-2">
        <input className={inputClass} placeholder={placeholder} value={name} onChange={(e) => setName(e.target.value)} />
        <button type="button" disabled={saving || !name} onClick={save} className={buttonClass}><Plus size={15} /></button>
      </div>
      <ListRows rows={rows} saving={saving} remove={(id) => run(() => remove(id), `${title} removido.`)} />
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
  const [form, setForm] = useState({ name: "", document: "", phone: "", email: "", notes: "" });
  const save = () => run(
    () => inventoryApi.createSupplier({ ...form, active: true }),
    "Fornecedor cadastrado.",
  ).then(() => setForm({ name: "", document: "", phone: "", email: "", notes: "" }));

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Novo fornecedor</h3>
        <div className="mt-4 space-y-3">
          <input className={inputClass} placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className={inputClass} placeholder="Documento" value={form.document} onChange={(e) => setForm({ ...form, document: e.target.value })} />
          <input className={inputClass} placeholder="Telefone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <input className={inputClass} placeholder="E-mail" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <textarea className={inputClass} placeholder="Observacoes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving || !form.name} onClick={save} className={buttonClass}><Plus size={15} /> Cadastrar</button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <TableHeader columns={["Fornecedor", "Contato", "Documento", ""]} />
        {data.suppliers.map((item) => (
          <div key={item.id} className="grid grid-cols-[1.4fr_1.3fr_1fr_auto] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.name}</span>
            <span className="text-stone">{item.phone || item.email || "-"}</span>
            <span className="text-stone">{item.document || "-"}</span>
            <DeleteButton disabled={saving} onClick={() => run(() => inventoryApi.removeSupplier(item.id), "Fornecedor removido.")} />
          </div>
        ))}
        {!data.suppliers.length && <EmptyRow text="Nenhum fornecedor cadastrado." />}
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

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Nova compra em rascunho</h3>
        <div className="mt-4 space-y-3">
          <select className={inputClass} value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}>
            <option value="">Fornecedor</option>
            {data.suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <input className={inputClass} placeholder="Numero da nota/pedido" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} />
          <input className={inputClass} type="date" value={form.expected_date} onChange={(e) => setForm({ ...form, expected_date: e.target.value })} />
          <select className={inputClass} value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })}>
            <option value="">Item</option>
            {data.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} type="number" min="0.001" step="0.001" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
            <input className={inputClass} type="number" min="0" step="0.01" value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: Number(e.target.value) })} />
          </div>
          <p className="text-sm font-bold text-stone">Total: {currency(total)}</p>
          <textarea className={inputClass} placeholder="Observacoes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving} onClick={save} className={buttonClass}><Plus size={15} /> Salvar rascunho</button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <TableHeader columns={["Compra", "Fornecedor", "Itens", "Total", ""]} />
        {data.purchases.map((item) => (
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
        {!data.purchases.length && <EmptyRow text="Nenhuma compra cadastrada." />}
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

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Novo movimento manual</h3>
        <div className="mt-4 space-y-3">
          <select className={inputClass} value={form.movement_type} onChange={(e) => setForm({ ...form, movement_type: e.target.value as "in" | "out", reason: e.target.value === "out" ? "manual_out" : "initial_stock" })}>
            <option value="in">Entrada de estoque</option>
            <option value="out">Saida de estoque</option>
          </select>
          <select className={inputClass} value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })}>
            <option value="">Item</option>
            {data.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select className={inputClass} value={form.location_id} onChange={(e) => setForm({ ...form, location_id: e.target.value })}>
            <option value="">Local</option>
            {data.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputClass} type="number" min="0.001" step="0.001" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
            <input className={inputClass} type="number" min="0" step="0.01" value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: Number(e.target.value) })} />
          </div>
          <input className={inputClass} placeholder="Motivo" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          <textarea className={inputClass} placeholder="Observacoes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving || !form.item_id} onClick={save} className={buttonClass}><Plus size={15} /> Registrar movimento</button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <TableHeader columns={["Item", "Tipo", "Local", "Quantidade", "Custo", ""]} />
        {data.manual_entries.map((item) => (
          <div key={item.id} className="grid grid-cols-[1.2fr_.8fr_1fr_.8fr_.8fr_auto] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm">
            <span className="font-bold text-cream">{item.item_name || item.item_id}</span>
            <span className={item.movement_type === "out" ? "font-bold text-red-300" : "font-bold text-emerald-300"}>{item.movement_type === "out" ? "Saida" : "Entrada"}</span>
            <span className="text-stone">{item.location_name || "-"}</span>
            <span className="text-stone">{item.quantity}</span>
            <span className="text-stone">{currency(item.unit_cost)}</span>
            <DeleteButton disabled={saving} onClick={() => run(() => inventoryApi.removeManualEntry(item.id), "Entrada manual removida.")} />
          </div>
        ))}
        {!data.manual_entries.length && <EmptyRow text="Nenhuma entrada manual registrada." />}
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
  rows: Array<{ id: string; name: string }>;
  saving: boolean;
  remove: (id: string) => void;
}) {
  return (
    <div className="mt-4 space-y-2">
      {rows.map((row) => (
        <div key={row.id} className="flex items-center justify-between gap-3 rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-sm">
          <span className="font-semibold text-cream">{row.name}</span>
          <DeleteButton disabled={saving} onClick={() => remove(row.id)} />
        </div>
      ))}
      {!rows.length && <p className="rounded-lg border border-surface-03 bg-surface-02 px-3 py-4 text-center text-sm text-stone">Sem registros.</p>}
    </div>
  );
}
