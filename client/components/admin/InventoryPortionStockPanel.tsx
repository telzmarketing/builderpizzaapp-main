import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { inventoryApi, type InventoryPortionBalance, type InventoryPortionReplenishment } from "@/lib/api";

export default function InventoryPortionStockPanel() {
  const [rows, setRows] = useState<InventoryPortionBalance[]>([]);
  const [alerts, setAlerts] = useState<InventoryPortionReplenishment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([inventoryApi.portionBalances(), inventoryApi.portionReplenishmentAlerts()])
      .then(([balances, replenishment]) => { setRows(balances); setAlerts(replenishment.filter((row) => row.status === "alert")); })
      .catch((err) => setError(err instanceof Error ? err.message : "Falha ao carregar estoque porcionado."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-black text-cream">Estoque Porcionado</h2>
          <p className="mt-1 text-sm text-stone">Saldo derivado das movimentações oficiais de cada produto porcionado.</p>
        </div>
        <button type="button" className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone hover:bg-surface-03 hover:text-cream" onClick={load}>
          <RefreshCw size={15} /> Atualizar
        </button>
      </div>

      {alerts.length > 0 && <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4"><h3 className="font-black text-amber-100">Alertas de reposição</h3>{alerts.map((row) => <p key={row.config_id} className="text-sm text-amber-100">{row.output_item_name}: disponível {row.available_stock}, em preparo {row.in_preparation}; sugeridas {row.suggested_portions} porções — matéria-prima estimada {row.estimated_source_quantity} {row.unit_symbol || "unid."}.</p>)}</div>}

      {loading ? (
        <div className="flex min-h-40 items-center justify-center text-stone"><Loader2 size={18} className="mr-2 animate-spin" />Carregando saldos...</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-surface-03">
          <div className="grid min-w-[1100px] grid-cols-[1.4fr_1.2fr_.7fr_1fr_1fr_1fr_1fr_1fr] gap-3 bg-surface-01 px-4 py-3 text-xs font-black uppercase tracking-wide text-stone">
            <span>Produto porcionado</span><span>Origem</span><span>Unidade</span><span>Físico</span><span>Reservado</span><span>Disponível</span><span>Em preparo</span><span>Custo / validade</span>
          </div>
          {rows.map((row) => (
            <div key={row.config_id} className={`grid min-w-[1100px] grid-cols-[1.4fr_1.2fr_.7fr_1fr_1fr_1fr_1fr_1fr] gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm ${row.available_stock <= row.min_stock ? "bg-amber-500/5" : ""}`}>
              <span className="font-bold text-cream">{row.output_item_name}<small className="block text-stone">mínimo {row.min_stock} · alvo {row.target_stock}</small></span>
              <span className="text-stone">{row.source_item_name || "-"}</span>
              <span className="text-stone">{row.unit_symbol || "-"}</span>
              <span className="text-stone">{row.physical_stock}</span>
              <span className="text-stone">{row.reserved_stock}</span>
              <span className={row.available_stock <= row.min_stock ? "font-bold text-amber-200" : "text-emerald-200"}>{row.available_stock}</span>
              <span className="text-stone">{row.in_preparation}</span>
              <span className="text-stone">{row.unit_cost.toFixed(2)}{row.next_expiry ? ` · ${new Date(row.next_expiry).toLocaleDateString("pt-BR")}` : ""}</span>
            </div>
          ))}
          {!rows.length && <p className="px-4 py-10 text-center text-sm text-stone">Nenhum produto porcionado ativo.</p>}
        </div>
      )}
      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}
    </section>
  );
}
