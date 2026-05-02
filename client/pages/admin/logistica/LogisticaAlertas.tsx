import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, AlertTriangle, CheckCircle2, MapPin, Clock } from "lucide-react";
import { deliveryApi, type DeliveryAlert } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  assigned:   "Designado",
  picked_up:  "Coletado",
  on_the_way: "A caminho",
};

const STATUS_CLS: Record<string, string> = {
  assigned:   "bg-blue-500/15 text-blue-300",
  picked_up:  "bg-gold/15 text-gold",
  on_the_way: "bg-violet-500/15 text-violet-300",
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

export default function LogisticaAlertas() {
  const [alerts, setAlerts] = useState<DeliveryAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");
    try {
      const data = await deliveryApi.getAlerts();
      setAlerts(data ?? []);
      setLastUpdated(new Date());
    } catch {
      setError("Não foi possível verificar os alertas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(() => load(true), 30_000);
    return () => window.clearInterval(id);
  }, [load]);

  const criticalCount = alerts.filter((a) => a.overdue_minutes >= 15).length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-cream font-bold text-lg flex items-center gap-2">
            Alertas de Atraso
            {alerts.length > 0 && (
              <span className="rounded-full bg-red-500 text-white text-xs font-black px-2 py-0.5">
                {alerts.length}
              </span>
            )}
          </h3>
          <p className="text-stone text-sm mt-0.5">
            Entregas que ultrapassaram o tempo estimado · atualiza a cada 30s
            {lastUpdated && (
              <span className="ml-2 text-stone/60">
                (última atualização {lastUpdated.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })})
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => load()}
          className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-stone text-sm hover:text-cream transition-colors"
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

      {/* Critical alert banner */}
      {!loading && criticalCount > 0 && (
        <div className="mb-5 flex items-center gap-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3">
          <AlertTriangle size={18} className="text-red-400 flex-shrink-0" />
          <p className="text-red-300 text-sm font-medium">
            {criticalCount === 1
              ? "1 entrega está atrasada há mais de 15 minutos. Contate o motoboy."
              : `${criticalCount} entregas estão atrasadas há mais de 15 minutos. Contate os motoboys.`}
          </p>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={36} className="animate-spin text-gold" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-center">
          <CheckCircle2 size={48} className="text-green-400 mb-4" />
          <p className="text-cream font-bold">Todas as entregas estão no prazo</p>
          <p className="text-stone text-sm mt-1">Nenhuma entrega ultrapassou o tempo estimado.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => {
            const statusCls = STATUS_CLS[a.status] ?? "bg-stone/20 text-stone";
            const borderCls = urgencyBorder(a.overdue_minutes);
            const textCls = urgencyCls(a.overdue_minutes);

            return (
              <div key={a.id} className={`rounded-2xl border p-5 ${borderCls}`}>
                <div className="flex items-start justify-between gap-3 mb-3">
                  {/* Left: order + driver */}
                  <div>
                    <p className="text-cream font-mono text-sm font-bold">
                      #{a.order_id.slice(0, 8).toUpperCase()}
                    </p>
                    {a.person_name && (
                      <p className="text-stone text-xs mt-0.5">
                        {a.person_name}
                        {a.person_phone && ` · ${a.person_phone}`}
                      </p>
                    )}
                  </div>

                  {/* Right: status badge */}
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold flex-shrink-0 ${statusCls}`}>
                    {STATUS_LABELS[a.status] ?? a.status}
                  </span>
                </div>

                {/* Delivery address */}
                {a.delivery_street && (
                  <div className="flex items-start gap-1.5 text-xs text-stone mb-3">
                    <MapPin size={11} className="flex-shrink-0 mt-0.5" />
                    <span className="line-clamp-1">{a.delivery_street}</span>
                  </div>
                )}

                {/* Timing info */}
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
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
