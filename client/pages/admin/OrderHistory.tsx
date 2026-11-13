import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, History, Loader2, RefreshCw, X } from "lucide-react";
import { marketplaceSettlementsApi, ordersApi, type ApiMarketplaceSettlementInput, type ApiOrder } from "@/lib/api";

const appOrigins = new Set(["partner_99", "ifood", "keeta"]);
const originLabels: Record<string, string> = { partner_99: "99Food", ifood: "iFood", keeta: "Keeta", own: "Próprio" };
const statusLabels: Record<string, string> = { delivered: "Entregue", cancelled: "Cancelado", paid: "Pago", preparing: "Preparando", on_the_way: "A caminho" };

function canReconcile(order: ApiOrder) {
  return appOrigins.has(String(order.order_origin || "")) && order.status === "delivered" && Boolean(order.delivered_at);
}

export default function OrderHistory() {
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [search, setSearch] = useState("");
  const [origin, setOrigin] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ApiOrder | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ApiMarketplaceSettlementInput>({ provider: "ifood", gross_amount: 0, expected_net_amount: 0, received_net_amount: 0, status: "received" });

  async function load() {
    setLoading(true); setError("");
    try { setOrders(await ordersApi.history({ search: search || undefined, order_origin: origin || undefined, limit: 100 })); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível carregar o histórico."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  const visible = useMemo(() => orders, [orders]);
  function openSettlement(order: ApiOrder) {
    const provider = (order.order_origin === "partner_99" ? "partner_99" : order.order_origin) as ApiMarketplaceSettlementInput["provider"];
    setSelected(order);
    setForm({ provider, gross_amount: Number(order.total || 0), expected_net_amount: Number(order.total || 0), received_net_amount: 0, status: "received" });
  }
  async function saveSettlement(event: React.FormEvent) {
    event.preventDefault(); if (!selected) return;
    setSaving(true); setError("");
    try {
      await marketplaceSettlementsApi.create(selected.id, form, crypto.randomUUID());
      setSelected(null); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível salvar a conciliação."); }
    finally { setSaving(false); }
  }

  return <main className="mx-auto w-full max-w-6xl p-5">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border-color)] pb-4">
      <div><p className="text-xs font-bold uppercase tracking-widest text-[var(--color-primary)]">Operações</p><h1 className="text-2xl font-black">Histórico de Pedidos</h1><p className="text-sm text-[var(--text-secondary)]">Pedidos canônicos e conciliação de repasses após a entrega.</p></div>
      <button onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg border border-[var(--border-color)] px-4 py-2 font-bold"><RefreshCw size={16} /> Atualizar</button>
    </header>
    {error && <div role="alert" className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}
    <section className="mt-5 rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-4"><div className="grid gap-3 md:grid-cols-[1fr_220px_auto]"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Número, cliente ou pedido do app" className="rounded-lg border border-[var(--border-color)] bg-transparent p-3" /><select value={origin} onChange={(event) => setOrigin(event.target.value)} className="rounded-lg border border-[var(--border-color)] bg-transparent p-3"><option value="">Todas as origens</option><option value="partner_99">99Food</option><option value="keeta">Keeta</option><option value="ifood">iFood</option><option value="own">Próprio</option></select><button onClick={() => void load()} className="rounded-lg bg-[var(--color-primary)] px-5 py-3 font-black text-white">Filtrar</button></div></section>
    <section className="mt-5 overflow-hidden rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)]"><div className="border-b border-[var(--border-color)] p-4"><h2 className="font-black">Pedidos</h2><p className="text-sm text-[var(--text-secondary)]">{loading ? "Carregando..." : `${visible.length} pedido(s)`}</p></div>{loading ? <div className="p-6"><Loader2 className="animate-spin" /></div> : visible.length === 0 ? <p className="p-6 text-sm text-[var(--text-secondary)]">Nenhum pedido encontrado.</p> : <div className="divide-y divide-[var(--border-color)]">{visible.map((order) => <article key={order.id} className="grid gap-3 p-4 lg:grid-cols-[1.2fr_1fr_1fr_auto] lg:items-center"><div><p className="font-black">#{order.partner_order_number || order.order_code || order.id.slice(0, 8)}</p><p className="text-sm">{order.delivery_name || "Cliente não informado"}</p><p className="text-xs text-[var(--text-secondary)]">{originLabels[String(order.order_origin || "own")] || String(order.order_origin || "Próprio")} · {statusLabels[String(order.status)] || String(order.status)}</p></div><div className="text-sm"><p className="font-bold">Itens</p><p className="text-[var(--text-secondary)]">{(order.items || []).map((item) => `${item.quantity}x ${item.product_name || "Produto"}`).join(", ") || "Sem itens"}</p></div><div className="text-sm"><p className="font-bold">Total</p><p>R$ {Number(order.total || 0).toFixed(2).replace(".", ",")}</p><p className="text-xs text-[var(--text-secondary)]">{order.delivered_at ? new Date(order.delivered_at).toLocaleString("pt-BR") : "Ainda não entregue"}</p></div>{canReconcile(order) ? <button onClick={() => openSettlement(order)} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-black text-white">Conciliar repasse</button> : <span className="text-xs text-[var(--text-secondary)]">Conciliação após entrega</span>}</article>)}</div>}</section>
    {selected && <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"><form onSubmit={saveSettlement} className="w-full max-w-2xl rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5"><div className="flex items-start justify-between"><div><h2 className="text-xl font-black">Conciliação do repasse</h2><p className="text-sm text-[var(--text-secondary)]">Pedido #{selected.partner_order_number || selected.order_code}</p></div><button type="button" onClick={() => setSelected(null)} aria-label="Fechar"><X size={18} /></button></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm font-bold">Plataforma<select value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value as ApiMarketplaceSettlementInput["provider"] })} className="mt-1 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-2"><option value="partner_99">99Food</option><option value="keeta">Keeta</option><option value="ifood">iFood</option></select></label>{(["gross_amount", "store_discount_amount", "marketplace_discount_amount", "delivery_fee", "service_fee", "commission_amount", "tax_amount", "expected_net_amount", "received_net_amount"] as const).map((name) => <label key={name} className="text-sm font-bold">{name.replaceAll("_", " ")}<input type="number" step="0.01" value={String(form[name] ?? 0)} onChange={(event) => setForm({ ...form, [name]: Number(event.target.value) })} className="mt-1 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-2" /></label>)}</div><label className="mt-3 block text-sm font-bold">Referência do repasse<input value={form.external_settlement_reference || ""} onChange={(event) => setForm({ ...form, external_settlement_reference: event.target.value })} className="mt-1 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-2" /></label><label className="mt-3 block text-sm font-bold">Observação<textarea value={form.notes || ""} onChange={(event) => setForm({ ...form, notes: event.target.value })} className="mt-1 w-full rounded-lg border border-[var(--border-color)] bg-transparent p-2" /></label><button disabled={saving} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[var(--color-primary)] px-5 py-3 font-black text-white disabled:opacity-50">{saving ? <Loader2 className="animate-spin" size={16} /> : <CheckCircle2 size={16} />} Salvar conciliação</button></form></div>}
  </main>;
}
