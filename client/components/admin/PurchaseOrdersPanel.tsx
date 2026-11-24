import { useMemo, useState } from "react";
import { CheckCircle2, Plus, Trash2 } from "lucide-react";
import { InventoryTableControls, filterAndSort } from "./InventoryTableControls";
import { inventoryApi, type InventoryOverview, type InventoryPurchase, type InventoryPurchaseItem } from "@/lib/api";
import { formatQuantity } from "@/lib/formatQuantity";

const inputClass = "min-w-0 w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none transition placeholder:text-stone/70 focus:border-gold";
const buttonClass = "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60";
const quantity = (value: number | string | null | undefined) => formatQuantity(value, "0");
const currency = (value: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
const purchaseDisplayName = (purchase: InventoryPurchase) => purchase.title?.trim() || purchase.name?.trim() || purchase.id;

export default function PurchaseOrdersPanel({
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
  const [form, setForm] = useState({ supplier_id: "", invoice_number: "", expected_date: "", notes: "", item_id: "", quantity: 1, unit_cost: 0 });
  const total = useMemo(() => form.quantity * form.unit_cost, [form.quantity, form.unit_cost]);
  const visiblePurchases = useMemo(
    () => filterAndSort(data.purchases, search, sort, {
      reference: (item) => `${purchaseDisplayName(item)} ${item.invoice_number || ""} ${item.supplier_name || ""} ${item.id}`,
      total_amount: (item) => item.total_amount ?? 0,
    }),
    [data.purchases, search, sort],
  );

  const save = () => {
    const items: InventoryPurchaseItem[] = form.item_id ? [{ item_id: form.item_id, quantity: form.quantity, unit_cost: form.unit_cost }] : [];
    return run(
      () => inventoryApi.createPurchase({ supplier_id: form.supplier_id || null, status: "draft", invoice_number: form.invoice_number || null, expected_date: form.expected_date || null, notes: form.notes || null, items }),
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
      items: purchase.items.map((item) => ({ item_id: item.item_id, quantity: item.quantity, unit_cost: item.unit_cost })),
    }),
    "Compra confirmada. O Financeiro criara a conta a pagar se a automacao estiver habilitada.",
  );

  return (
    <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
        <h3 className="text-sm font-black uppercase tracking-wide text-parchment">Nova compra em rascunho</h3>
        <div className="mt-4 space-y-3">
          <label className="block text-sm text-stone">Fornecedor<select className={inputClass} value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}><option value="">Selecione o fornecedor</option>{data.suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="block text-sm text-stone">Número da nota ou pedido<input className={inputClass} placeholder="Ex.: NF 12345" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></label>
          <label className="block text-sm text-stone">Data prevista de recebimento<input className={inputClass} type="date" value={form.expected_date} onChange={(e) => setForm({ ...form, expected_date: e.target.value })} /></label>
          <label className="block text-sm text-stone">Insumo<select className={inputClass} value={form.item_id} onChange={(e) => setForm({ ...form, item_id: e.target.value })}><option value="">Selecione o insumo</option>{data.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <div className="grid grid-cols-2 gap-2"><label className="block text-sm text-stone">Quantidade<input aria-label="Quantidade da compra" className={inputClass} type="number" min="0.001" step="0.001" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} /></label><label className="block text-sm text-stone">Custo unitário (R$)<input aria-label="Custo unitário da compra" className={inputClass} type="number" min="0" step="0.01" value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: Number(e.target.value) })} /></label></div>
          <p className="text-sm font-bold text-stone">Total: {currency(total)}</p>
          <textarea className={inputClass} placeholder="Observações" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <button type="button" disabled={saving} onClick={save} className={buttonClass}><Plus size={15} /> Salvar rascunho</button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border border-surface-03">
        <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "reference", label: "Compra (A-Z)" }, { value: "total_amount", label: "Valor total" }]} />
        <div className="hidden grid-cols-[1fr_1fr_2.2fr_.8fr_auto] gap-4 bg-surface-03 px-4 py-3 text-xs font-black uppercase tracking-wide text-stone lg:grid"><span>Compra</span><span>Fornecedor</span><span>Itens</span><span>Total</span><span>Ações</span></div>
        {visiblePurchases.map((item) => <div key={item.id} className="grid gap-4 border-t border-surface-03 bg-surface-01 px-4 py-4 text-sm lg:grid-cols-[1fr_1fr_2.2fr_.8fr_auto]"><span className="font-bold text-cream">{purchaseDisplayName(item)}{item.invoice_number && <small className="block font-normal text-stone">Nota fiscal/pedido: {item.invoice_number}</small>}<small className="block font-normal text-stone">{item.status === "confirmed" ? "Confirmada" : item.status === "requested" ? "Solicitada" : "Rascunho"}</small></span><span className="text-stone">{item.supplier_name || "-"}</span><div className="space-y-2">{item.items.length ? item.items.map((row) => { const detail = data.items.find((candidate) => candidate.id === row.item_id); return <div key={row.id || row.item_id} className="grid grid-cols-[minmax(0,1.5fr)_auto_auto_auto] items-center gap-3 rounded border border-surface-03 bg-surface-02 px-3 py-2 text-xs"><span className="min-w-0 truncate text-cream">{row.item_name || detail?.name || row.item_id}</span><span className="text-stone">{quantity(row.quantity)}</span><span className="text-stone">{currency(row.unit_cost)}</span><span className="font-bold text-cream">{currency(row.total_cost ?? row.quantity * row.unit_cost)}</span></div>; }) : <span className="text-stone">Nenhum item informado.</span>}</div><span className="text-stone">{currency(item.total_amount)}</span><span className="flex items-center gap-2">{item.status !== "confirmed" && <button type="button" disabled={saving} onClick={() => confirmPurchase(item)} className="rounded-lg border border-emerald-500/30 p-2 text-emerald-300" title="Confirmar compra"><CheckCircle2 size={16} /></button>}{item.status !== "confirmed" && <button type="button" disabled={saving} onClick={() => void run(() => inventoryApi.removePurchase(item.id), "Compra removida.")} className="rounded-lg border border-red-500/30 p-2 text-red-300" title="Remover compra"><Trash2 size={16} /></button>}</span></div>)}
        {!visiblePurchases.length && <div className="p-6 text-center text-sm text-stone">{data.purchases.length ? "Nenhuma compra encontrada." : "Nenhuma compra cadastrada."}</div>}
      </div>
    </div>
  );
}
