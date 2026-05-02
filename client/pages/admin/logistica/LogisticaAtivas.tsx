import { useCallback, useEffect, useState } from "react";
import { Loader2, MapPin, RefreshCw, Route } from "lucide-react";
import { deliveryApi, type DeliveryRecord } from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending_assignment: "Aguardando motoboy",
  assigned:           "Designado",
  picked_up:          "Coletado",
  on_the_way:         "A caminho",
  delivered:          "Entregue",
  completed:          "Finalizado",
  failed:             "Falhou",
  cancelled:          "Cancelado",
};

const STATUS_CLS: Record<string, string> = {
  assigned:    "bg-blue-500/15 text-blue-300",
  picked_up:   "bg-gold/15 text-gold",
  on_the_way:  "bg-violet-500/15 text-violet-300",
  delivered:   "bg-green-500/15 text-green-300",
  completed:   "bg-green-500/15 text-green-300",
};

function formatTime(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export default function LogisticaAtivas() {
  const [deliveries, setDeliveries] = useState<DeliveryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await deliveryApi.listActive();
      setDeliveries(data ?? []);
      setError("");
    } catch {
      setError("Não foi possível carregar as entregas ativas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(() => load(true), 15_000);
    return () => window.clearInterval(id);
  }, [load]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-cream font-bold text-lg">Entregas Ativas</h3>
          <p className="text-stone text-sm mt-0.5">Pedidos em rota agora · atualiza a cada 15s</p>
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

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={36} className="animate-spin text-gold" />
        </div>
      ) : deliveries.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-center">
          <Route size={48} className="text-stone mb-4" />
          <p className="text-cream font-bold">Nenhuma entrega em andamento</p>
          <p className="text-stone text-sm mt-1">As entregas aparecerão aqui quando atribuídas.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {deliveries.map((d) => {
            const statusCls = STATUS_CLS[d.status] ?? "bg-stone/20 text-stone";
            return (
              <div key={d.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-5">
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div>
                    <p className="text-cream font-mono text-sm font-bold">
                      #{d.order_id.slice(0, 8).toUpperCase()}
                    </p>
                    <p className="text-stone text-xs mt-0.5">
                      Entrega #{d.id.slice(0, 8).toUpperCase()}
                    </p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold flex-shrink-0 ${statusCls}`}>
                    {STATUS_LABELS[d.status] ?? d.status}
                  </span>
                </div>

                <div className="space-y-1.5 text-xs text-stone">
                  <div className="flex items-center gap-2">
                    <MapPin size={11} className="flex-shrink-0" />
                    <span>Atribuído: {formatTime(d.assigned_at)}</span>
                  </div>
                  {d.picked_up_at && (
                    <div className="flex items-center gap-2">
                      <MapPin size={11} className="flex-shrink-0" />
                      <span>Coletado: {formatTime(d.picked_up_at)}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Route size={11} className="flex-shrink-0" />
                    <span>Previsão: {d.estimated_minutes} min</span>
                  </div>
                </div>

                {d.confirmation_code && (
                  <div className="mt-4 rounded-xl bg-surface-03/60 p-3 text-center">
                    <p className="text-stone text-[10px] uppercase tracking-widest mb-1">Código de confirmação</p>
                    <p className="text-gold font-mono text-2xl font-black tracking-[0.3em]">
                      {d.confirmation_code}
                    </p>
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
