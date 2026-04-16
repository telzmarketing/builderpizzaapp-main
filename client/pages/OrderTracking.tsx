import { useSearchParams, Link, useNavigate } from "react-router-dom";
import { ChevronLeft, Loader2 } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { useEffect, useState, useCallback } from "react";
import { ordersApi, type ApiOrder, type OrderStatus } from "@/lib/api";

// Steps shown in the progress bar (subset of all statuses)
const PROGRESS_STEPS: OrderStatus[] = ["preparing", "on_the_way", "delivered"];

function stepIndex(status: OrderStatus): number {
  if (["pending", "waiting_payment", "paid"].includes(status)) return -1;
  return PROGRESS_STEPS.indexOf(status as OrderStatus);
}

export default function OrderTracking() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { siteContent } = useApp();
  const orderId = searchParams.get("orderId");
  const t = siteContent.pages.tracking;

  const [order, setOrder] = useState<ApiOrder | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState("");

  const fetchOrder = useCallback(async () => {
    if (!orderId) return;
    try {
      const data = await ordersApi.get(orderId);
      setOrder(data);
    } catch {
      setNotFound(true);
      setLoadError("Pedido não encontrado.");
    }
  }, [orderId]);

  // Initial fetch
  useEffect(() => { fetchOrder(); }, [fetchOrder]);

  // Poll every 15 seconds while order is not in a terminal state
  useEffect(() => {
    const terminal: OrderStatus[] = ["delivered", "cancelled", "refunded"];
    if (!order || terminal.includes(order.status)) return;
    const id = setInterval(fetchOrder, 15_000);
    return () => clearInterval(id);
  }, [order, fetchOrder]);

  const currentStepIndex = order ? stepIndex(order.status) : -1;
  const statusLabel = order ? (t.statusLabels[order.status] ?? order.status) : "";
  const statusDescription = order ? (t.statusDescriptions[order.status] ?? "") : "";
  const estimatedText = order
    ? t.estimatedTimeText.replace("{time}", String(order.estimated_time))
    : "";

  if (!orderId || notFound) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
        <div className="bg-slate-800 px-4 py-2 flex justify-between items-center text-xs text-slate-400">
          <span>10:20</span>
          <div className="flex gap-1"><span>📡</span><span>📶</span><span>🔋</span></div>
        </div>
        <div className="bg-slate-900 px-4 py-4 flex justify-between items-center sticky top-0 z-30">
          <button onClick={() => navigate(-1)} className="text-slate-300 hover:text-white transition-colors">
            <ChevronLeft size={24} />
          </button>
          <h1 className="text-white font-bold flex-1 text-center">{t.pageTitle}</h1>
          <div className="w-6" />
        </div>
        <div className="flex-1 flex items-center justify-center px-4 py-16">
          <div className="text-center">
            <div className="text-6xl mb-4">📦</div>
            <h2 className="text-2xl font-bold text-white mb-2">Pedido não encontrado</h2>
            <p className="text-slate-400 mb-6">{loadError || "Faça um pedido para acompanhar aqui."}</p>
            <Link to="/" className="inline-block bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 px-6 rounded-full transition-colors">
              Ir para o início
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950 flex items-center justify-center">
        <Loader2 size={40} className="animate-spin text-orange-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
      {/* Status Bar */}
      <div className="bg-slate-800 px-4 py-2 flex justify-between items-center text-xs text-slate-400">
        <span>10:20</span>
        <div className="flex gap-1"><span>📡</span><span>📶</span><span>🔋</span></div>
      </div>

      {/* Header */}
      <div className="bg-slate-900 px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-slate-300 hover:text-white transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="text-white font-bold flex-1 text-center">{t.pageTitle}</h1>
        <div className="w-6" />
      </div>

      <div className="px-4 pt-6 pb-32">
        {/* Order Number */}
        <div className="text-center mb-8">
          <p className="text-slate-400 text-sm">{t.orderNumberLabel}</p>
          <p className="text-3xl font-bold text-white mt-2 font-mono">
            {order.id.slice(0, 8).toUpperCase()}
          </p>
        </div>

        {/* Estimated Time */}
        <div className="text-center mb-8">
          <p className="text-slate-400 text-sm">{estimatedText}</p>
        </div>

        {/* Progress Bar — only shown when order is past "paid" state */}
        {currentStepIndex >= -1 && !["cancelled", "refunded"].includes(order.status) && (
          <div className="mb-8">
            <div className="flex items-center gap-4 mb-6">
              {PROGRESS_STEPS.map((step, index) => (
                <div key={step} className="flex-1 flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 transition-colors ${
                      index <= currentStepIndex
                        ? "bg-orange-500 text-white font-bold"
                        : "bg-slate-700 text-slate-400"
                    }`}
                  >
                    {index < currentStepIndex ? "✓" : index + 1}
                  </div>
                  <p className={`text-xs text-center font-medium ${index <= currentStepIndex ? "text-white" : "text-slate-400"}`}>
                    {t.statusLabels[step] ?? step}
                  </p>
                </div>
              ))}
            </div>
            <div className="flex gap-4 px-4">
              {[...Array(PROGRESS_STEPS.length - 1)].map((_, i) => (
                <div key={i} className={`flex-1 h-1 rounded-full transition-colors ${i < currentStepIndex ? "bg-orange-500" : "bg-slate-700"}`} />
              ))}
            </div>
          </div>
        )}

        {/* Active Status */}
        <div className="text-center mb-2">
          <p className={`font-bold text-lg ${order.status === "cancelled" || order.status === "refunded" ? "text-red-400" : "text-orange-500"}`}>
            {statusLabel}
          </p>
        </div>
        {statusDescription && (
          <div className="text-center mb-8">
            <p className="text-slate-400 text-sm">{statusDescription}</p>
          </div>
        )}

        {/* Items Ordered */}
        <div className="mb-6">
          <h3 className="text-white font-bold mb-4 text-lg">Itens do Pedido</h3>
          <div className="space-y-3">
            {order.items.map((item) => {
              const isMulti = item.flavor_division > 1;
              const displayIcons = item.flavors.map((f) => f.icon).join("");
              const displayName = isMulti
                ? item.flavors.map((f) => f.name).join(" + ")
                : item.product_name;
              const divLabel =
                item.flavor_division === 2
                  ? "Meio a Meio"
                  : item.flavor_division === 3
                  ? "3 Sabores"
                  : "Inteira";
              return (
                <div key={item.id} className="bg-slate-800 rounded-xl p-4 flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-slate-700 flex-shrink-0 flex items-center justify-center text-lg">
                    {displayIcons || "🍕"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-white font-semibold text-sm leading-tight">{displayName}</h4>
                    <p className="text-slate-400 text-xs mt-0.5">
                      {item.quantity}x · {item.selected_size} · {divLabel}
                    </p>
                  </div>
                  <p className="text-orange-500 font-bold text-sm flex-shrink-0">
                    R$ {(item.final_price * item.quantity).toFixed(2)}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Order Summary */}
          <div className="bg-slate-800 rounded-xl p-4 mt-6 space-y-3 border border-slate-700">
            <div className="flex justify-between text-slate-300 text-sm">
              <span>Subtotal:</span>
              <span>R$ {order.subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-slate-300 text-sm">
              <span>Taxa de entrega:</span>
              <span>R$ {order.shipping_fee.toFixed(2)}</span>
            </div>
            {order.discount > 0 && (
              <div className="flex justify-between text-green-400 text-sm">
                <span>Desconto:</span>
                <span>-R$ {order.discount.toFixed(2)}</span>
              </div>
            )}
            <div className="border-t border-slate-700 pt-3 flex justify-between">
              <span className="text-white font-bold">Total:</span>
              <span className="text-orange-500 font-bold text-lg">R$ {order.total.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Buttons */}
      <div className="fixed bottom-0 left-0 right-0 bg-slate-950 border-t border-slate-800 px-4 py-4">
        <div className="flex gap-3">
          <Link
            to="/pedidos"
            className="flex-1 border-2 border-orange-500 text-orange-500 font-bold py-3 px-4 rounded-full transition-colors hover:bg-orange-500/10 active:scale-95 text-center text-sm"
          >
            Meus Pedidos
          </Link>
          <Link
            to="/"
            className="flex-1 border-2 border-slate-600 text-slate-300 font-bold py-3 px-4 rounded-full transition-colors hover:border-slate-500 active:scale-95 text-center text-sm"
          >
            Cardápio
          </Link>
        </div>
      </div>
    </div>
  );
}
