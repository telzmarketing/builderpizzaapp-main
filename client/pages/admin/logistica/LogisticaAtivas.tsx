import { useCallback, useEffect, useState } from "react";
import { Loader2, MapPin, RefreshCw, Route, Clock, Zap } from "lucide-react";
import { deliveryApi, type DeliveryRecord } from "@/lib/api";

function etaText(assignedAt?: string, estimatedMinutes?: number): { text: string; urgent: boolean } | null {
  if (!assignedAt || !estimatedMinutes) return null;
  const deadline = new Date(assignedAt).getTime() + estimatedMinutes * 60_000;
  const remaining = Math.round((deadline - Date.now()) / 60_000);
  if (remaining < 0) return { text: `${Math.abs(remaining)}min atrasado`, urgent: true };
  return { text: `${remaining}min restantes`, urgent: remaining <= 5 };
}

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
  const [autoAssigning, setAutoAssigning] = useState(false);
  const [autoAssignMsg, setAutoAssignMsg] = useState("");

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
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h3 className="text-cream font-bold text-lg">Entregas Ativas</h3>
          <p className="text-stone text-sm mt-0.5">Pedidos em rota agora · atualiza a cada 15s</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              setAutoAssigning(true);
              setAutoAssignMsg("");
              try {
                const result = await deliveryApi.autoAssign();
                const n = result?.length ?? 0;
                setAutoAssignMsg(n > 0 ? `${n} entrega(s) atribuída(s)` : "Nenhuma entrega pendente ou sem motoboys disponíveis");
                if (n > 0) load(true);
                setTimeout(() => setAutoAssignMsg(""), 4000);
              } catch {
                setAutoAssignMsg("Erro ao executar auto-atribuição.");
                setTimeout(() => setAutoAssignMsg(""), 3000);
              } finally {
                setAutoAssigning(false);
              }
            }}
            disabled={autoAssigning}
            className="flex items-center gap-1.5 rounded-xl border border-gold/40 bg-gold/10 px-3 py-2 text-gold text-sm hover:bg-gold/20 disabled:opacity-50 transition-colors"
            title="Atribuir motoboys disponíveis a pedidos aguardando designação"
          >
            {autoAssigning ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            Auto-atribuir
          </button>
          <button
            onClick={() => load()}
            className="flex items-center gap-1.5 rounded-xl border border-surface-03 px-3 py-2 text-stone text-sm hover:text-cream transition-colors"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Atualizar
          </button>
        </div>
      </div>

      {autoAssignMsg && (
        <div className="mb-4 rounded-xl border border-gold/30 bg-gold/10 px-4 py-3 text-sm text-gold">
          {autoAssignMsg}
        </div>
      )}

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

                {/* Endereço de entrega */}
                {d.order?.delivery_street && (
                  <div className="flex items-start gap-1.5 text-xs text-stone mb-3">
                    <MapPin size={11} className="flex-shrink-0 mt-0.5" />
                    <span className="line-clamp-2">
                      {d.order.delivery_street}
                      {d.order.delivery_complement ? `, ${d.order.delivery_complement}` : ""}
                      {d.order.delivery_city ? ` — ${d.order.delivery_city}` : ""}
                    </span>
                  </div>
                )}

                <div className="space-y-1.5 text-xs text-stone">
                  <div className="flex items-center gap-2">
                    <Clock size={11} className="flex-shrink-0" />
                    <span>Atribuído: {formatTime(d.assigned_at)}</span>
                  </div>
                  {d.picked_up_at && (
                    <div className="flex items-center gap-2">
                      <Route size={11} className="flex-shrink-0" />
                      <span>Coletado: {formatTime(d.picked_up_at)}</span>
                    </div>
                  )}
                  {(() => {
                    const eta = etaText(d.assigned_at, d.estimated_minutes);
                    if (!eta) return null;
                    return (
                      <div className={`flex items-center gap-2 font-medium ${eta.urgent ? "text-orange-300" : "text-green-300"}`}>
                        <Clock size={11} className="flex-shrink-0" />
                        <span>{eta.text}</span>
                      </div>
                    );
                  })()}
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
