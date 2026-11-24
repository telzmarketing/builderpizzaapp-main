import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { inventoryApi, type PurchaseReceipt } from "@/lib/api";

const statusLabel: Record<PurchaseReceipt["status"], string> = { draft: "Rascunho", submitted: "Em conferência", posted: "Publicado no estoque", rejected: "Rejeitado" };

export default function PurchaseReceiptPanel() {
  const [rows, setRows] = useState<PurchaseReceipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setLoading(true); setError("");
    inventoryApi.listPurchaseReceipts().then(setRows).catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar os recebimentos.")).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);
  return <section className="space-y-4 rounded-xl border border-surface-03 bg-surface-02 p-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-black text-cream">Recebimentos de mercadorias</h2><p className="text-sm text-stone">Conferências físicas separadas da validação fiscal; somente publicados alteram o estoque.</p></div><button className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone hover:text-cream" onClick={load} disabled={loading}><RefreshCw size={16} className={loading ? "animate-spin" : ""} />Atualizar</button></div>
    {error && <p className="rounded-lg border border-red-900/50 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}
    {!loading && !error && rows.length === 0 && <p className="rounded-lg border border-dashed border-surface-03 p-6 text-center text-sm text-stone">Nenhum recebimento registrado.</p>}
    <div className="grid gap-3 md:grid-cols-2">{rows.map((row) => <article key={row.id} className="rounded-lg border border-surface-03 bg-surface-01 p-4"><div className="flex items-center justify-between gap-3"><strong className="text-cream">{row.purchase_id}</strong><span className="text-xs font-bold text-gold">{statusLabel[row.status]}</span></div><p className="mt-2 text-xs text-stone">{row.items.length} item(ns) · versão {row.version} · {new Date(row.received_at).toLocaleString("pt-BR")}</p><ul className="mt-3 space-y-1 text-sm text-stone">{row.items.map((item) => <li key={item.id}>{item.item_name}: {item.quantity_received} recebido(s), {item.quantity_rejected} recusado(s){item.lot_code ? ` · lote ${item.lot_code}` : ""}{item.quality_status && item.quality_status !== "accepted" ? ` · qualidade ${item.quality_status}` : ""}</li>)}</ul></article>)}</div>
  </section>;
}
