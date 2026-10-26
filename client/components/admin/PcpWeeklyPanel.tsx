import { useEffect, useRef, useState } from "react";
import { ApiRequestError, pcpApi, productsApi, type ApiEffectivePermissions, type PcpWeeklyPlan } from "@/lib/api";

const field = "min-h-11 rounded-lg border border-surface-03 bg-surface-01 p-2 text-cream";
const button = "min-h-11 rounded-lg border border-surface-03 px-4 font-bold disabled:opacity-40";

export function canManagePcp(permissions: ApiEffectivePermissions | null): boolean {
  return !!(permissions?.is_master || permissions?.modules.inventory?.manage);
}

function currentWeek() {
  const date = new Date();
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export default function PcpWeeklyPanel() {
  const [week, setWeek] = useState(currentWeek);
  const [sourceWeeks, setSourceWeeks] = useState(4);
  const [plan, setPlan] = useState<PcpWeeklyPlan | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const sequence = useRef(0);
  const [manage] = useState(() => {
    try { return canManagePcp(JSON.parse(localStorage.getItem("admin_permissions") || "null")); } catch { return false; }
  });

  useEffect(() => {
    let cancelled = false;
    productsApi.list(false).then((products) => { if (!cancelled) setNames(Object.fromEntries(products.map((product) => [product.id, product.name]))); }).catch(() => { /* Missing catalog names never become invented product data. */ });
    return () => { cancelled = true; sequence.current += 1; };
  }, []);

  async function run(action: () => Promise<PcpWeeklyPlan>, success: string) {
    const request = ++sequence.current;
    setBusy(true); setError(""); setMessage("");
    try {
      const next = await action();
      if (request === sequence.current) { setPlan(next); setMessage(success); }
    } catch (caught) {
      if (request !== sequence.current) return;
      setPlan(null);
      if (caught instanceof ApiRequestError && caught.code === "PcpPlanNotFound") setMessage("Nenhuma previs�o gerada para esta semana.");
      else setError(caught instanceof Error ? caught.message : "N�o foi poss�vel carregar o planejamento.");
    } finally { if (request === sequence.current) setBusy(false); }
  }

  return <section className="space-y-4 rounded-xl border border-surface-03 bg-surface-01 p-4">
    <div><h3 className="font-black text-cream">PCP - previs�o semanal</h3><p className="mt-1 text-sm text-stone">Sugest�es calculadas pelo servidor a partir de pedidos conclu�dos. Aprovar registra a decis�o do gestor; este contrato n�o cria ordens de preparo.</p></div>
    <div className="flex flex-wrap items-end gap-3"><label className="flex flex-col gap-1 text-sm">In�cio da semana<input type="date" className={field} disabled={busy} value={week} onChange={(event) => { setWeek(event.target.value); setPlan(null); setMessage(""); setError(""); }} /></label>
      <label className="flex flex-col gap-1 text-sm">Semanas do hist�rico<input type="number" min={1} max={52} className={field} disabled={busy} value={sourceWeeks} onChange={(event) => setSourceWeeks(Number(event.target.value))} /></label>
      <button className={button} disabled={busy || !week} onClick={() => void run(() => pcpApi.get(week), "Previs�o carregada.")}>Consultar</button>
      {manage && <button className={button} disabled={busy || !week || sourceWeeks < 1 || sourceWeeks > 52 || plan?.status === "approved"} onClick={() => void run(() => pcpApi.generate({ week_start: week, source_weeks: sourceWeeks }), "Previs�o gerada. Revise antes de aprovar.")}>Gerar previs�o</button>}
    </div>
    {busy && <p role="status" className="text-stone">Processando planejamento...</p>}
    {error && <p role="alert" className="text-red-300">{error}</p>}
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    {!busy && !plan && !error && !message && <p className="text-sm text-stone">Selecione a semana e consulte uma previs�o existente ou gere uma sugest�o.</p>}
    {plan && <><p className="text-sm text-stone">Situa��o: <b className="text-cream">{plan.status === "approved" ? "Aprovado" : plan.status === "draft" ? "Rascunho" : plan.status}</b> � Hist�rico: {plan.source_window_start} a {plan.source_window_end}</p>
      {plan.suggestions?.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-2">Produto</th><th className="p-2">Quantidade semanal sugerida</th><th className="p-2">Origem</th></tr></thead><tbody>{plan.suggestions.map((row) => <tr key={row.product_id} className="border-t border-surface-03"><td className="p-2">{names[row.product_id] || "Produto indispon�vel no cat�logo"}</td><td className="p-2">{row.suggested_quantity}</td><td className="p-2">{row.source === "completed_orders" ? "Pedidos conclu�dos" : row.source}</td></tr>)}</tbody></table></div> : <p className="text-sm text-stone">Sem pedidos conclu�dos suficientes no per�odo consultado. Nenhuma quantidade foi estimada na interface.</p>}
      {plan.approved_at && <p className="text-sm text-stone">Aprova��o registrada em {new Date(plan.approved_at).toLocaleString("pt-BR")}.</p>}
      {manage && plan.status === "draft" && <button className={`${button} bg-gold text-black`} disabled={busy} onClick={() => void run(() => pcpApi.approve(plan.week_start, plan.status), "Planejamento aprovado pelo gestor.")}>Aprovar planejamento revisado</button>}
    </>}
  </section>;
}
