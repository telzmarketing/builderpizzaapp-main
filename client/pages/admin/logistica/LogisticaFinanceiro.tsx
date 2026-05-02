import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCw, DollarSign, CheckCircle2, Clock, ChevronDown, ChevronUp } from "lucide-react";
import { deliveryApi, type DeliveryEarning, type DeliveryPerson } from "@/lib/api";

function todayStr() {
  return new Date().toISOString().split("T")[0];
}

function monthStart(offset = 0) {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth() + offset, 1).toISOString().split("T")[0];
}

function monthEnd(offset = 0) {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth() + offset + 1, 0).toISOString().split("T")[0];
}

function fmtBRL(value: number) {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtDate(iso?: string) {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString("pt-BR");
}

type Period = "current" | "last" | "custom";

export default function LogisticaFinanceiro() {
  const [period, setPeriod] = useState<Period>("current");
  const [customFrom, setCustomFrom] = useState(monthStart());
  const [customTo, setCustomTo] = useState(todayStr());
  const [personFilter, setPersonFilter] = useState("");
  const [persons, setPersons] = useState<DeliveryPerson[]>([]);
  const [earnings, setEarnings] = useState<DeliveryEarning[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [paying, setPaying] = useState(false);
  const [expandedDrivers, setExpandedDrivers] = useState<Set<string>>(new Set());

  const { from, to } = useMemo(() => {
    if (period === "current") return { from: monthStart(), to: monthEnd() };
    if (period === "last") return { from: monthStart(-1), to: monthEnd(-1) };
    return { from: customFrom, to: customTo };
  }, [period, customFrom, customTo]);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const [e, p] = await Promise.all([
        deliveryApi.listEarnings({ person_id: personFilter || undefined, period_from: from, period_to: to }),
        persons.length === 0 ? deliveryApi.listPersons() : Promise.resolve(persons),
      ]);
      setEarnings(e ?? []);
      if (persons.length === 0) setPersons(p ?? []);
    } catch {
      setError("Não foi possível carregar os dados financeiros.");
    } finally {
      setLoading(false);
    }
  }, [from, to, personFilter, persons]);

  useEffect(() => { load(); }, [from, to, personFilter]);

  // Group by driver
  const grouped = useMemo(() => {
    const map = new Map<string, { person_name: string; person_phone: string; items: DeliveryEarning[] }>();
    for (const e of earnings) {
      const key = e.delivery_person_id;
      if (!map.has(key)) {
        map.set(key, {
          person_name: e.person_name ?? "Motoboy desconhecido",
          person_phone: e.person_phone ?? "",
          items: [],
        });
      }
      map.get(key)!.items.push(e);
    }
    return Array.from(map.entries()).map(([id, val]) => ({ id, ...val }));
  }, [earnings]);

  const totalPending = earnings.filter((e) => e.status === "pending").reduce((s, e) => s + e.amount, 0);
  const totalPaid    = earnings.filter((e) => e.status === "paid").reduce((s, e) => s + e.amount, 0);

  const pendingEarnings = earnings.filter((e) => e.status === "pending");

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function selectAllPending() {
    setSelectedIds(new Set(pendingEarnings.map((e) => e.id)));
  }

  function selectDriverPending(driverId: string) {
    const ids = earnings.filter((e) => e.delivery_person_id === driverId && e.status === "pending").map((e) => e.id);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.add(id));
      return next;
    });
  }

  async function handlePay() {
    if (selectedIds.size === 0) return;
    setPaying(true);
    try {
      await deliveryApi.payEarnings(Array.from(selectedIds));
      setSelectedIds(new Set());
      await load(true);
    } catch {
      setError("Erro ao registrar pagamentos.");
    } finally {
      setPaying(false);
    }
  }

  async function payDriver(driverId: string) {
    const ids = earnings.filter((e) => e.delivery_person_id === driverId && e.status === "pending").map((e) => e.id);
    if (ids.length === 0) return;
    setPaying(true);
    try {
      await deliveryApi.payEarnings(ids);
      await load(true);
    } catch {
      setError("Erro ao registrar pagamentos.");
    } finally {
      setPaying(false);
    }
  }

  function toggleDriverExpand(id: string) {
    setExpandedDrivers((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-cream font-bold text-lg">Financeiro</h3>
          <p className="text-stone text-sm mt-0.5">Liquidações e repasses PIX por motoboy</p>
        </div>
        <button
          onClick={() => load()}
          className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-stone text-sm hover:text-cream transition-colors"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Atualizar
        </button>
      </div>

      {/* Period + filter row */}
      <div className="flex flex-wrap gap-3 mb-5">
        {/* Period tabs */}
        <div className="flex rounded-xl overflow-hidden border border-surface-03">
          {(["current", "last", "custom"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-2 text-xs font-medium transition-colors ${
                period === p ? "bg-gold text-cream" : "bg-surface-02 text-stone hover:text-cream"
              }`}
            >
              {p === "current" ? "Este mês" : p === "last" ? "Mês anterior" : "Personalizado"}
            </button>
          ))}
        </div>

        {/* Custom range */}
        {period === "custom" && (
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="rounded-lg border border-surface-03 bg-surface-02 text-cream text-xs px-3 py-2"
            />
            <span className="text-stone text-xs">até</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="rounded-lg border border-surface-03 bg-surface-02 text-cream text-xs px-3 py-2"
            />
          </div>
        )}

        {/* Driver filter */}
        <select
          value={personFilter}
          onChange={(e) => setPersonFilter(e.target.value)}
          className="rounded-xl border border-surface-03 bg-surface-02 text-stone text-xs px-3 py-2 hover:text-cream"
        >
          <option value="">Todos os motoboys</option>
          {persons.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        <div className="rounded-2xl border border-surface-03 bg-surface-02 px-5 py-4 text-center">
          <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Pendente</p>
          <p className="text-orange-300 text-xl font-black">{fmtBRL(totalPending)}</p>
        </div>
        <div className="rounded-2xl border border-surface-03 bg-surface-02 px-5 py-4 text-center">
          <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Pago</p>
          <p className="text-green-300 text-xl font-black">{fmtBRL(totalPaid)}</p>
        </div>
        <div className="rounded-2xl border border-surface-03 bg-surface-02 px-5 py-4 text-center sm:col-span-1 col-span-2">
          <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Total</p>
          <p className="text-gold text-xl font-black">{fmtBRL(totalPending + totalPaid)}</p>
        </div>
      </div>

      {/* Bulk action bar */}
      {pendingEarnings.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 mb-5 rounded-xl border border-surface-03 bg-surface-02 px-4 py-3">
          <span className="text-stone text-sm">
            {selectedIds.size > 0 ? `${selectedIds.size} selecionado(s)` : "Selecione para pagar"}
          </span>
          <button
            onClick={selectAllPending}
            className="text-xs text-gold hover:text-gold/80 font-medium"
          >
            Selecionar todos pendentes
          </button>
          {selectedIds.size > 0 && (
            <button
              onClick={handlePay}
              disabled={paying}
              className="ml-auto flex items-center gap-1.5 rounded-xl bg-gold px-4 py-2 text-xs font-bold text-cream hover:bg-gold/90 disabled:opacity-50 transition-colors"
            >
              {paying ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
              Pagar selecionados
            </button>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={36} className="animate-spin text-gold" />
        </div>
      ) : grouped.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-center">
          <DollarSign size={48} className="text-stone mb-4" />
          <p className="text-cream font-bold">Nenhum registro encontrado</p>
          <p className="text-stone text-sm mt-1">
            Não há lançamentos para o período selecionado.
            {!personFilter && " Configure o valor por entrega nas Configurações para registrar automaticamente."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {grouped.map((group) => {
            const groupPending = group.items.filter((e) => e.status === "pending");
            const groupPendingTotal = groupPending.reduce((s, e) => s + e.amount, 0);
            const groupPaidTotal = group.items.filter((e) => e.status === "paid").reduce((s, e) => s + e.amount, 0);
            const expanded = expandedDrivers.has(group.id);

            return (
              <div key={group.id} className="rounded-2xl border border-surface-03 bg-surface-02 overflow-hidden">
                {/* Driver header */}
                <div
                  className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-surface-03/30 transition-colors"
                  onClick={() => toggleDriverExpand(group.id)}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-cream font-bold text-sm">{group.person_name}</p>
                    <p className="text-stone text-xs">{group.person_phone}</p>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0">
                    {groupPendingTotal > 0 && (
                      <span className="text-orange-300 text-sm font-bold">
                        {fmtBRL(groupPendingTotal)} pendente
                      </span>
                    )}
                    {groupPaidTotal > 0 && (
                      <span className="text-green-300 text-sm font-bold">
                        {fmtBRL(groupPaidTotal)} pago
                      </span>
                    )}
                    {groupPendingTotal > 0 && (
                      <button
                        onClick={(e) => { e.stopPropagation(); payDriver(group.id); }}
                        disabled={paying}
                        className="flex items-center gap-1 rounded-lg bg-gold/20 text-gold text-xs font-bold px-3 py-1.5 hover:bg-gold/30 disabled:opacity-50 transition-colors"
                      >
                        <CheckCircle2 size={12} />
                        Pagar tudo
                      </button>
                    )}
                    {expanded ? <ChevronUp size={14} className="text-stone" /> : <ChevronDown size={14} className="text-stone" />}
                  </div>
                </div>

                {/* Earnings list */}
                {expanded && (
                  <div className="border-t border-surface-03">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-stone border-b border-surface-03">
                          <th className="px-5 py-2 text-left w-8">
                            <input
                              type="checkbox"
                              checked={groupPending.length > 0 && groupPending.every((e) => selectedIds.has(e.id))}
                              onChange={() => {
                                const allSelected = groupPending.every((e) => selectedIds.has(e.id));
                                setSelectedIds((prev) => {
                                  const next = new Set(prev);
                                  groupPending.forEach((e) => allSelected ? next.delete(e.id) : next.add(e.id));
                                  return next;
                                });
                              }}
                              className="accent-gold"
                              disabled={groupPending.length === 0}
                            />
                          </th>
                          <th className="px-2 py-2 text-left">Data</th>
                          <th className="px-2 py-2 text-left">Entrega</th>
                          <th className="px-2 py-2 text-right">Valor</th>
                          <th className="px-2 py-2 text-center">Status</th>
                          <th className="px-4 py-2 text-right">Pago por</th>
                        </tr>
                      </thead>
                      <tbody>
                        {group.items.map((e) => (
                          <tr key={e.id} className="border-b border-surface-03/50 hover:bg-surface-03/20">
                            <td className="px-5 py-2.5">
                              {e.status === "pending" && (
                                <input
                                  type="checkbox"
                                  checked={selectedIds.has(e.id)}
                                  onChange={() => toggleSelect(e.id)}
                                  className="accent-gold"
                                />
                              )}
                            </td>
                            <td className="px-2 py-2.5 text-stone">{fmtDate(e.period_date)}</td>
                            <td className="px-2 py-2.5 text-parchment font-mono">
                              #{e.delivery_id.slice(0, 8).toUpperCase()}
                            </td>
                            <td className="px-2 py-2.5 text-right text-cream font-bold">{fmtBRL(e.amount)}</td>
                            <td className="px-2 py-2.5 text-center">
                              {e.status === "pending" ? (
                                <span className="inline-flex items-center gap-1 rounded-full bg-orange-500/15 text-orange-300 px-2 py-0.5 text-[10px] font-bold">
                                  <Clock size={9} />
                                  Pendente
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 text-green-300 px-2 py-0.5 text-[10px] font-bold">
                                  <CheckCircle2 size={9} />
                                  Pago
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-right text-stone">
                              {e.paid_by ?? "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
