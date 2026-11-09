import { useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCw, Send } from "lucide-react";
import { inventoryApi, type InventoryPortionBalance, type InventoryPortionReplenishment } from "@/lib/api";
import { formatQuantity } from "@/lib/formatQuantity";
import { filterAndSort, InventoryTableControls } from "./InventoryTableControls";

function formatExactQuantity(value: number | string | null | undefined) {
  return formatQuantity(value);
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
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"name" | "available" | "in_preparation">("name");

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([inventoryApi.portionBalances(), inventoryApi.portionReplenishmentAlerts()])
      .then(([balances, replenishment]) => { setRows(balances); setAlerts(replenishment); })
      .catch((err) => setError(err instanceof Error ? err.message : "Falha ao carregar estoque porcionado."))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const visibleRows = useMemo(() => filterAndSort(rows, search, sort, { name: (row) => `${row.output_item_name} ${row.source_item_name || ""}`, available: (row) => numericQuantity(row.available_stock), in_preparation: (row) => numericQuantity(row.in_preparation) }), [rows, search, sort]);
  const conversionAlerts = useMemo(() => new Map(alerts.map((row) => [row.config_id, row])), [alerts]);
  const visibleAlerts = alerts.filter((row) => row.status === "alert" || row.conversion_error);

  const requestPreparation = async (row: InventoryPortionBalance) => {
    const quantity = requestQuantities[row.config_id] || String(Math.max(0, numericQuantity(row.target_stock) - numericQuantity(row.available_stock) - numericQuantity(row.in_preparation)));
    if (numericQuantity(quantity) <= 0) return;
    const conversionError = conversionAlerts.get(row.config_id)?.conversion_error;
    if (conversionError) { setError(conversionError); return; }
    setSavingId(row.config_id);
    setError("");
    setMessage("");
    try {
      await inventoryApi.requestPortionPreparation(row.config_id, { target_quantity: quantity, notes: "Solicitação criada no Estoque de Porcionamento." }, crypto.randomUUID());
      setRequestQuantities((current) => ({ ...current, [row.config_id]: "" }));
      setMessage("Solicitação de porcionamento enviada para Preparo.");
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
      {visibleAlerts.length > 0 && <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4"><h3 className="font-black text-amber-100">Alertas de reposição</h3>{visibleAlerts.map((row) => <p key={row.config_id} className="text-sm text-amber-100">{row.output_item_name}: disponível {formatExactQuantity(row.available_stock)} porções, em preparo {formatExactQuantity(row.in_preparation)} porções; sugeridas {formatExactQuantity(row.suggested_portions)} porções — matéria-prima estimada {row.conversion_error ? "não calculada" : `${formatExactQuantity(row.estimated_source_quantity)} ${row.source_unit_symbol || "unid."}`}{row.conversion_error ? ` — conversão pendente: ${row.conversion_error}` : ""}.</p>)}</div>}
      <p className="rounded-md border border-surface-03 bg-surface-01 px-3 py-2 text-xs text-stone">As quantidades deste painel são porções produzidas. O saldo da matéria-prima, como KG de Calabresa, é controlado separadamente.</p>
      {loading ? <div className="flex min-h-40 items-center justify-center text-stone"><Loader2 size={18} className="mr-2 animate-spin" />Carregando saldos...</div> : (
        <div className="overflow-x-auto rounded-lg border border-surface-03">
          <p className="border-b border-surface-03 bg-surface-01 px-4 py-2 text-xs font-bold uppercase tracking-wide text-stone">Físico, reservado, disponível e em preparo: porções</p>
          <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "name", label: "Produto (A-Z)" }, { value: "available", label: "Disponível" }, { value: "in_preparation", label: "Em preparo" }]} />
          <div className="grid min-w-[1180px] grid-cols-[1.45fr_1.05fr_.55fr_.7fr_.7fr_.75fr_.7fr_1.1fr_1.25fr] gap-2 bg-surface-01 px-4 py-3 text-xs font-black uppercase tracking-wide text-stone"><span>Produto porcionado</span><span>Origem</span><span>Unidade</span><span>Físico</span><span>Reservado</span><span>Disponível</span><span>Em preparo</span><span>Custo / validade</span><span>Ação</span></div>
          {visibleRows.map((row) => <div key={row.config_id} className={`grid min-w-[1180px] grid-cols-[1.45fr_1.05fr_.55fr_.7fr_.7fr_.75fr_.7fr_1.1fr_1.25fr] items-center gap-2 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm ${numericQuantity(row.available_stock) <= numericQuantity(row.min_stock) ? "bg-amber-500/5" : ""}`}>
            <span className="font-bold text-cream">{row.output_item_name}<small className="block text-stone">mínimo {formatExactQuantity(row.min_stock)} · alvo {formatExactQuantity(row.target_stock)} porções</small>{row.legacy_output_unit && <small className="block text-amber-300">Cadastro legado: a unidade técnica de peso também consta como unidade de saída. Revise antes de executar novas ordens.</small>}</span>
            <span className="text-stone">{row.source_item_name || "-"}{row.source_stock != null && <small className="block text-gold">Bruto: {formatExactQuantity(row.source_stock)} {row.source_unit_symbol || "unid."}</small>}</span><span className="text-stone">PRQ</span><span className="text-stone">{formatExactQuantity(row.physical_stock)}</span><span className="text-stone">{formatExactQuantity(row.reserved_stock)}</span><span className={numericQuantity(row.available_stock) <= numericQuantity(row.min_stock) ? "font-bold text-amber-200" : "text-emerald-200"}>{formatExactQuantity(row.available_stock)}</span><span className="text-stone">{formatExactQuantity(row.in_preparation)}</span><span className="text-stone">{numericQuantity(row.unit_cost).toFixed(2)}{row.next_expiry ? ` · ${new Date(row.next_expiry).toLocaleDateString("pt-BR")}` : ""}</span>
            <div className="flex min-w-0 items-center gap-1"><input aria-label={`Quantidade de ${row.output_item_name}`} className="w-16 rounded-md border border-surface-03 bg-surface-02 px-2 py-1 text-xs text-cream" type="number" min="0.000001" step="0.000001" value={requestQuantities[row.config_id] ?? ""} placeholder={formatExactQuantity(Math.max(0, numericQuantity(row.target_stock) - numericQuantity(row.available_stock) - numericQuantity(row.in_preparation)))} onChange={(event) => setRequestQuantities((current) => ({ ...current, [row.config_id]: event.target.value }))} disabled={row.usage === "direct"} /><button type="button" title="Solicitar Porcionamento" aria-label="Solicitar Porcionamento" className="inline-flex items-center gap-1 rounded-md bg-gold px-2 py-1 text-xs font-black text-black disabled:opacity-60" disabled={savingId === row.config_id || row.usage === "direct"} onClick={() => void requestPreparation(row)}>{savingId === row.config_id ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}<span className="hidden xl:inline">Solicitar</span></button></div>
          </div>)}
          {!visibleRows.length && <p className="px-4 py-10 text-center text-sm text-stone">{rows.length ? "Nenhum produto encontrado." : "Nenhum produto porcionado ativo."}</p>}
        </div>
      )}
      {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}
      {message && <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{message}</p>}
    </section>
  );
}
