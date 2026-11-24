import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { inventoryApi, type PurchasePlanning, type PurchasePlanningNeed } from "@/lib/api";
import { formatQuantity } from "@/lib/formatQuantity";

const buttonClass = "inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone transition hover:bg-surface-03 hover:text-cream disabled:cursor-not-allowed disabled:opacity-60";

const stateLabels: Record<PurchasePlanningNeed["state"], string> = {
  confirmed: "Confirmado",
  pending: "Pendente",
  estimated: "Estimado",
  blocked: "Bloqueado",
  unavailable: "Indisponível",
};

const actionLabels: Record<PurchasePlanningNeed["action"], string> = {
  covered: "Coberto",
  purchase_required: "Compra necessária",
  review_required: "Revisão necessária",
};

function stateClass(state: PurchasePlanningNeed["state"]) {
  if (state === "blocked" || state === "unavailable") return "border-red-500/30 bg-red-500/10 text-red-200";
  if (state === "estimated" || state === "pending") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
}

function StateIcon({ state }: { state: PurchasePlanningNeed["state"] }) {
  if (state === "blocked" || state === "unavailable") return <ShieldAlert size={15} />;
  if (state === "estimated" || state === "pending") return <Clock3 size={15} />;
  return <CheckCircle2 size={15} />;
}

const quantity = (value: number) => formatQuantity(value, "0");

export default function PurchasePlanningPanel() {
  const [planning, setPlanning] = useState<PurchasePlanning | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    inventoryApi.planningNeeds()
      .then(setPlanning)
      .catch((err) => setError(err instanceof Error ? err.message : "Não foi possível carregar o planejamento."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-black text-cream">Planejamento de Necessidades</h2>
          <p className="mt-1 text-sm text-stone">Leitura consolidada de saldo, reservas, compras confirmadas e porcionamento. Nenhuma compra é criada automaticamente.</p>
        </div>
        <button type="button" onClick={load} className={buttonClass} disabled={loading}>
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} /> Atualizar
        </button>
      </div>

      {loading && <div className="flex min-h-40 items-center justify-center text-stone"><Loader2 size={18} className="mr-2 animate-spin" /> Calculando necessidades...</div>}
      {error && <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-200"><AlertTriangle size={17} className="mt-0.5 shrink-0" /> {error}</div>}

      {!loading && !error && planning && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Summary label="Itens avaliados" value={planning.totals.total ?? planning.items.length} />
            <Summary label="Compras necessárias" value={planning.totals.purchase_required ?? 0} />
            <Summary label="Revisões necessárias" value={planning.totals.review_required ?? 0} />
          </div>
          {planning.items.length === 0 ? (
            <div className="rounded-lg border border-surface-03 px-4 py-8 text-center text-sm text-stone">Nenhum item ativo disponível para planejamento.</div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-surface-03">
              <table className="w-full min-w-[920px] text-left text-sm">
                <thead className="bg-surface-01 text-xs uppercase tracking-wide text-stone"><tr>
                  <th className="px-4 py-3">Item</th><th className="px-4 py-3">Disponível</th><th className="px-4 py-3">Mínimo</th><th className="px-4 py-3">Em trânsito</th><th className="px-4 py-3">Sugerido</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3">Motivo</th>
                </tr></thead>
                <tbody className="divide-y divide-surface-03">
                  {planning.items.map((item) => <tr key={`${item.source}-${item.item_id}`} className="align-top">
                    <td className="px-4 py-3"><div className="font-bold text-cream">{item.item_name}</div><div className="text-xs text-stone">{item.source === "portion" ? `Porcionamento de ${item.source_item_name ?? "origem não informada"}` : "Necessidade direta"}</div></td>
                    <td className="px-4 py-3 text-stone">{quantity(item.available_stock)} {item.unit_symbol ?? ""}</td>
                    <td className="px-4 py-3 text-stone">{quantity(item.minimum_stock)} {item.unit_symbol ?? ""}</td>
                    <td className="px-4 py-3 text-stone">{quantity(item.in_transit)} {item.unit_symbol ?? ""}</td>
                    <td className="px-4 py-3 font-bold text-cream">{quantity(item.suggested_quantity)} {item.unit_symbol ?? ""}</td>
                    <td className="px-4 py-3"><div className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-bold ${stateClass(item.state)}`}><StateIcon state={item.state} /> {stateLabels[item.state]}</div><div className="mt-1 text-xs text-stone">{actionLabels[item.action]}</div></td>
                    <td className="max-w-xs px-4 py-3 text-xs text-stone">{item.reason}</td>
                  </tr>)}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function Summary({ label, value }: { label: string; value: number }) {
  return <div className="rounded-lg border border-surface-03 bg-surface-01 px-4 py-3"><div className="text-xs uppercase tracking-wide text-stone">{label}</div><div className="mt-1 text-xl font-black text-cream">{value}</div></div>;
}
