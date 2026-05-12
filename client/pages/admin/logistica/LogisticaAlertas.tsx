import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, AlertTriangle, CheckCircle2, MapPin, Clock, Phone, X } from "lucide-react";
import { deliveryApi, type DeliveryAlert } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  assigned: "Designado",
  picked_up: "Coletado",
  on_the_way: "A caminho",
  failed: "Problema na entrega",
};

const STATUS_CLS: Record<string, string> = {
  assigned: "bg-blue-500/15 text-blue-300",
  picked_up: "bg-gold/15 text-gold",
  on_the_way: "bg-violet-500/15 text-violet-300",
  failed: "bg-red-500/15 text-red-300",
};

function urgencyCls(minutes: number) {
  if (minutes >= 30) return "text-red-400";
  if (minutes >= 15) return "text-orange-400";
  return "text-yellow-400";
}

function urgencyBorder(minutes: number) {
  if (minutes >= 30) return "border-red-500/40 bg-red-500/5";
  if (minutes >= 15) return "border-orange-500/40 bg-orange-500/5";
  return "border-yellow-500/40 bg-yellow-500/5";
}

function formatDateTime(iso?: string | null) {
  if (!iso) return "--";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function LogisticaAlertas() {
  const [alerts, setAlerts] = useState<DeliveryAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [resolving, setResolving] = useState<DeliveryAlert | null>(null);
  const [resolutionNote, setResolutionNote] = useState("");
  const [savingResolution, setSavingResolution] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await deliveryApi.getAlerts();
      setAlerts(data ?? []);
      setLastUpdated(new Date());
    } catch {
      setError("Nao foi possivel verificar os alertas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(() => load(true), 30_000);
    return () => window.clearInterval(id);
  }, [load]);

  const problemCount = alerts.filter((a) => a.alert_type === "problem").length;
  const criticalCount = alerts.filter((a) => a.alert_type !== "problem" && a.overdue_minutes >= 15).length;

  async function handleResolveProblem() {
    if (!resolving || resolutionNote.trim().length < 3) return;
    setSavingResolution(true);
    setError("");
    try {
      await deliveryApi.resolveProblem(resolving.id, resolutionNote.trim());
      setResolving(null);
      setResolutionNote("");
      await load(true);
    } catch {
      setError("Nao foi possivel registrar a resolucao do problema.");
    } finally {
      setSavingResolution(false);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-lg font-bold text-cream">
            Alertas de Entrega
            {alerts.length > 0 && (
              <span className="rounded-full bg-red-500 px-2 py-0.5 text-xs font-black text-white">
                {alerts.length}
              </span>
            )}
          </h3>
          <p className="mt-0.5 text-sm text-stone">
            Problemas reportados pelo motoboy e entregas atrasadas - atualiza a cada 30s
            {lastUpdated && (
              <span className="ml-2 text-stone/60">
                (ultima atualizacao {lastUpdated.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })})
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => load()}
          className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-sm text-stone transition-colors hover:text-cream"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Atualizar
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {!loading && problemCount > 0 && (
        <div className="mb-5 flex items-center gap-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3">
          <AlertTriangle size={18} className="shrink-0 text-red-400" />
          <p className="text-sm font-medium text-red-300">
            {problemCount === 1
              ? "1 entrega foi reportada com problema. Entre em contato com o cliente e registre a resolucao para o motoboy."
              : `${problemCount} entregas foram reportadas com problema. Entre em contato com os clientes e registre a resolucao para os motoboys.`}
          </p>
        </div>
      )}

      {!loading && criticalCount > 0 && (
        <div className="mb-5 flex items-center gap-3 rounded-xl border border-orange-500/40 bg-orange-500/10 px-4 py-3">
          <AlertTriangle size={18} className="shrink-0 text-orange-400" />
          <p className="text-sm font-medium text-orange-300">
            {criticalCount === 1
              ? "1 entrega esta atrasada ha mais de 15 minutos. Contate o motoboy."
              : `${criticalCount} entregas estao atrasadas ha mais de 15 minutos. Contate os motoboys.`}
          </p>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={36} className="animate-spin text-gold" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-center">
          <CheckCircle2 size={48} className="mb-4 text-green-400" />
          <p className="font-bold text-cream">Nenhum alerta de entrega</p>
          <p className="mt-1 text-sm text-stone">Sem problemas reportados e sem atrasos no momento.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => {
            const isProblem = a.alert_type === "problem";
            const statusCls = STATUS_CLS[a.status] ?? "bg-stone/20 text-stone";
            const borderCls = isProblem ? "border-red-500/50 bg-red-500/10" : urgencyBorder(a.overdue_minutes);
            const textCls = urgencyCls(a.overdue_minutes);

            return (
              <div key={a.id} className={`rounded-2xl border p-5 ${borderCls}`}>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-sm font-bold text-cream">
                      #{a.order_id.slice(0, 8).toUpperCase()}
                    </p>
                    {isProblem && (
                      <p className="mt-0.5 text-xs font-bold text-red-300">
                        Problema reportado {formatDateTime(a.problem_reported_at)}
                      </p>
                    )}
                    {a.person_name && (
                      <p className="mt-0.5 text-xs text-stone">
                        {a.person_name}
                        {a.person_phone && ` - ${a.person_phone}`}
                      </p>
                    )}
                  </div>

                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold ${statusCls}`}>
                    {STATUS_LABELS[a.status] ?? a.status}
                  </span>
                </div>

                {a.delivery_street && (
                  <div className="mb-3 flex items-start gap-1.5 text-xs text-stone">
                    <MapPin size={11} className="mt-0.5 shrink-0" />
                    <span className="line-clamp-1">{a.delivery_street}</span>
                  </div>
                )}

                {isProblem ? (
                  <div className="space-y-3 text-xs">
                    <div className="rounded-xl border border-red-500/20 bg-red-950/20 p-3">
                      <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-red-200">Relato do motoboy</p>
                      <p className="text-parchment">{a.problem_report || "Problema reportado sem descricao."}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-stone">
                      {a.delivery_name && <span>Cliente: <span className="text-cream">{a.delivery_name}</span></span>}
                      {a.delivery_phone && (
                        <a href={`tel:${a.delivery_phone}`} className="inline-flex items-center gap-1 rounded-lg border border-surface-03 px-2 py-1 text-parchment hover:border-gold/40 hover:text-gold">
                          <Phone size={11} /> {a.delivery_phone}
                        </a>
                      )}
                    </div>
                    <button
                      onClick={() => { setResolving(a); setResolutionNote(""); }}
                      className="flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-2 text-xs font-bold text-white transition-colors hover:bg-green-700"
                    >
                      <CheckCircle2 size={13} /> Informar resolucao ao motoboy
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-4 text-xs">
                    <div className="flex items-center gap-1.5 text-stone">
                      <Clock size={11} />
                      <span>Previsto: {a.estimated_minutes}min</span>
                    </div>
                    <div className={`flex items-center gap-1.5 font-bold ${textCls}`}>
                      <AlertTriangle size={11} />
                      <span>{a.overdue_minutes}min de atraso</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {resolving && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center">
          <div className="w-full max-w-lg rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-xl">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <p className="font-bold text-cream">Resolver problema da entrega</p>
                <p className="mt-1 text-xs text-stone">Pedido #{resolving.order_id.slice(0, 8).toUpperCase()}</p>
              </div>
              <button
                onClick={() => setResolving(null)}
                className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-03 text-stone hover:text-cream"
              >
                <X size={16} />
              </button>
            </div>
            <textarea
              value={resolutionNote}
              onChange={(e) => setResolutionNote(e.target.value)}
              rows={4}
              placeholder="Ex: Cliente contatado. Motoboy autorizado a retornar para finalizar a entrega."
              className="w-full resize-none rounded-xl border border-surface-03 bg-surface-01 p-3 text-sm text-cream placeholder-stone/60 outline-none focus:border-gold"
            />
            <button
              disabled={resolutionNote.trim().length < 3 || savingResolution}
              onClick={handleResolveProblem}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-green-600 py-3 text-sm font-black text-white hover:bg-green-700 disabled:opacity-50"
            >
              {savingResolution ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              Notificar motoboy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
