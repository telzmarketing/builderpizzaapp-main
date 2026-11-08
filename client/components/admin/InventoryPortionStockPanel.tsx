import { useEffect, useState } from "react";
import { Loader2, RefreshCw, Send } from "lucide-react";
import { inventoryApi, type InventoryPortionBalance, type InventoryPortionReplenishment } from "@/lib/api";

function formatExactQuantity(value: number | string | null | undefined) {
  if (value === null || value === undefined) return "-";
  const numeric = Number(String(value).trim().replace(",", "."));
  return Number.isFinite(numeric) ? numeric.toLocaleString("pt-BR", { useGrouping: false, maximumFractionDigits: 6 }) : "-";
}

function numericQuantity(value: number | string | null | undefined) {
  const numericValue = Number(String(value ?? 0).replace(",", "."));
  return Number.isFinite(numericValue) ? numericValue : 0;
}

export default function InventoryPortionStockPanel() {
  const [rows, setRows] = useState<InventoryPortionBalance[]>([]);
  const [alerts, setAlerts] = useState<InventoryPortionReplenishment[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [requestQuantities, setRequestQuantities] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([inventoryApi.portionBalances(), inventoryApi.portionReplenishmentAlerts()])
      .then(([balances, replenishment]) => { setRows(balances); setAlerts(replenishment.filter((row) => row.status === "alert")); })
      .catch((err) => setError(err instanceof Error ? err.message : "Falha ao carregar estoque porcionado."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const requestPreparation = async (row: InventoryPortionBalance) => {
    const quantity = requestQuantities[row.config_id] || String(Math.max(0, numericQuantity(row.target_stock) - numericQuantity(row.available_stock)));
    if (numericQuantity(quantity) <= 0) return;
    setSavingId(row.config_id);
    setError("");
    try {
      await inventoryApi.requestPortionPreparation(row.config_id, { target_quantity: quantity, notes: "Solicitação criada no Estoque de Porcionamento." }, crypto.randomUUID());
      setRequestQuantities((current) => ({ ...current, [row.config_id]: "" }));
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao solicitar porcionamento.");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
      <div className="flex items-center justify-between">
        <div><h2 className="text-lg font-black text-cream">Estoque Porcionado</h2><p className="mt-1 text-sm text-stone">Saldo derivado das movimentações oficiais de cada produto porcionado.</p></div>
        <button type="button" className="inline-flex items-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone hover:bg-surface-03 hover:text-cream" onClick={load}><RefreshCw size={15} /> Atualizar</button>
      </div>
      {alerts.length > 0 && <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4"><h3 className="font-black text-amber-100">Alertas de reposição</h3>{alerts.map((row) => <p key={row.config_id} className="text-sm text-amber-100">{row.output_item_name}: disponível {formatExactQuantity(row.available_stock)}, em preparo {formatExactQuantity(row.in_preparation)}; sugeridas {formatExactQuantity(row.suggested_portions)} porções — matéria-prima estimada {formatExactQuantity(row.estimated_source_quantity)} {row.unit_symbol || "unid."}.</p>)}</div>}
      {loading ? <div className="flex min-h-40 items-center justify-center text-stone"><Loader2 size={18} className="mr-2 animate-spin" />Carregando saldos...</div> : (
        <div className="overflow-x-auto rounded-lg border border-surface-03">
          <div className="grid min-w-[1180px] grid-cols-[1.45fr_1.05fr_.55fr_.7fr_.7fr_.75fr_.7fr_1.1fr_1.25fr] gap-2 bg-surface-01 px-4 py-3 text-xs font-black uppercase tracking-wide text-stone"><span>Produto porcionado</span><span>Origem</span><span>Unidade</span><span>Físico</span><span>Reservado</span><span>Disponível</span><span>Em preparo</span><span>Custo / validade</span><span>Ação</span></div>
          {rows.map((row) => <div key={row.config_id} className={`grid min-w-[1180px] grid-cols-[1.45fr_1.05fr_.55fr_.7fr_.7fr_.75fr_.7fr_1.1fr_1.25fr] items-center gap-2 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm ${numericQuantity(row.available_stock) <= numericQuantity(row.min_stock) ? "bg-amber-500/5" : ""}`}>
            <span className="font-bold text-cream">{row.output_item_name}<small className="block text-stone">mínimo {formatExactQuantity(row.min_stock)} · alvo {formatExactQuantity(row.target_stock)}</small></span>
            <span className="text-stone">{row.source_item_name || "-"}</span><span className="text-stone">{row.unit_symbol || "-"}</span><span className="text-stone">{formatExactQuantity(row.physical_stock)}</span><span className="text-stone">{formatExactQuantity(row.reserved_stock)}</span><span className={numericQuantity(row.available_stock) <= numericQuantity(row.min_stock) ? "font-bold text-amber-200" : "text-emerald-200"}>{formatExactQuantity(row.available_stock)}</span><span className="text-stone">{formatExactQuantity(row.in_preparation)}</span><span className="text-stone">{numericQuantity(row.unit_cost).toFixed(2)}{row.next_expiry ? ` · ${new Date(row.next_expiry).toLocaleDateString("pt-BR")}` : ""}</span>
            <div className="flex min-w-0 items-center gap-1"><input aria-label={`Quantidade de ${row.output_item_name}`} className="w-16 rounded-md border border-surface-03 bg-surface-02 px-2 py-1 text-xs text-cream" type="number" min="0.000001" step="0.000001" value={requestQuantities[row.config_id] ?? ""} placeholder={formatExactQuantity(Math.max(0, numericQuantity(row.target_stock) - numericQuantity(row.available_stock)))} onChange={(event) => setRequestQuantities((current) => ({ ...current, [row.config_id]: event.target.value }))} disabled={row.usage === "direct"} /><button type="button" title="Solicitar Porcionamento" aria-label="Solicitar Porcionamento" className="inline-flex items-center gap-1 rounded-md bg-gold px-2 py-1 text-xs font-black text-black disabled:opacity-60" disabled={savingId === row.config_id || row.usage === "direct"} onClick={() => void requestPreparation(row)}>{savingId === row.config_id ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}<span className="hidden xl:inline">Solicitar</span></button></div>
          </div>)}
          {!rows.length && <p className="px-4 py-10 text-center text-sm text-stone">Nenhum produto porcionado ativo.</p>}
        </div>
      )}
      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}
    </section>
  );
}
