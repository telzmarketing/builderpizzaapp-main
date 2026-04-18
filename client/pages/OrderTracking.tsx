import { useSearchParams, Link, useNavigate } from "react-router-dom";
import { ChevronLeft, Loader2 } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
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
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
        <div className="bg-surface-02 px-4 py-2 flex justify-between items-center text-xs text-stone">
          <span>10:20</span>
          <div className="flex gap-1"><span>📡</span><span>📶</span><span>🔋</span></div>
        </div>
        <div className="bg-brand-dark px-4 py-4 flex justify-between items-center sticky top-0 z-30">
          <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
            <ChevronLeft size={24} />
          </button>
          <MoschettieriLogo className="text-cream text-base" />
          <div className="w-6" />
        </div>
        <div className="flex-1 flex items-center justify-center px-4 py-16">
          <div className="text-center">
            <div className="text-6xl mb-4">📦</div>
            <h2 className="text-2xl font-bold text-cream mb-2">Pedido não encontrado</h2>
            <p className="text-stone mb-6">{loadError || "Faça um pedido para acompanhar aqui."}</p>
            <Link to="/" className="inline-block bg-gold hover:bg-gold/90 text-cream font-bold py-3 px-6 rounded-full transition-colors">
              Ir para o início
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 flex items-center justify-center">
        <Loader2 size={40} className="animate-spin text-gold" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="text-cream font-bold flex-1 text-center">{t.pageTitle}</h1>
        <div className="w-6" />
      </div>

      <div className="px-4 pt-6 pb-32">
        {/* Order Number */}
        <div className="text-center mb-2">
          <p className="text-stone text-sm">{t.orderNumberLabel}</p>
          <p className="text-6xl font-bold text-cream mt-1">
            {parseInt(order.id.slice(0, 8), 16) % 100}
          </p>
          <p className="text-stone text-sm mt-2">{estimatedText}</p>
        </div>

        {/* Progress Bar */}
        {!["cancelled", "refunded"].includes(order.status) && (
          <div className="mb-6 mt-8">
            <div className="flex items-center px-4">
              {PROGRESS_STEPS.map((step, index) => (
                <div key={step} className="flex items-center flex-1 last:flex-none">
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-4 h-4 rounded-full border-2 transition-colors ${
                        index <= currentStepIndex
                          ? "bg-gold border-gold"
                          : "bg-surface-02 border-brand-mid"
                      }`}
                    />
                  </div>
                  {index < PROGRESS_STEPS.length - 1 && (
                    <div className={`flex-1 h-0.5 transition-colors ${index < currentStepIndex ? "bg-gold" : "bg-surface-03"}`} />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active Status */}
        <div className="text-center mb-6">
          <p className={`font-bold text-xl ${order.status === "cancelled" || order.status === "refunded" ? "text-red-400" : "text-cream"}`}>
            {statusLabel}
          </p>
        </div>
        {statusDescription && (
          <div className="text-center mb-8">
            <p className="text-stone text-sm">{statusDescription}</p>
          </div>
        )}

        {/* Items Ordered */}
        <div className="mb-6">
          <h3 className="text-cream font-bold mb-4 text-lg">Itens do Pedido</h3>
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
                <div key={item.id} className="bg-surface-02 rounded-xl p-4 flex items-start gap-4">
                  <div className="w-12 h-12 rounded-full bg-surface-03 flex-shrink-0 flex items-center justify-center text-lg">
                    {displayIcons || "🍕"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-cream font-semibold text-sm leading-tight">{displayName}</h4>
                    <p className="text-stone text-xs mt-0.5">
                      {item.quantity}x · {item.selected_size} · {divLabel}
                    </p>
                  </div>
                  <p className="text-gold font-bold text-sm flex-shrink-0">
                    R$ {(item.final_price * item.quantity).toFixed(2)}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Order Summary */}
          <div className="bg-surface-02 rounded-xl p-4 mt-6 space-y-3 border border-surface-03">
            <div className="flex justify-between text-parchment text-sm">
              <span>Subtotal:</span>
              <span>R$ {order.subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-parchment text-sm">
              <span>Taxa de entrega:</span>
              <span>R$ {order.shipping_fee.toFixed(2)}</span>
            </div>
            {order.discount > 0 && (
              <div className="flex justify-between text-green-400 text-sm">
                <span>Desconto:</span>
                <span>-R$ {order.discount.toFixed(2)}</span>
              </div>
            )}
            <div className="border-t border-surface-03 pt-3 flex justify-between">
              <span className="text-cream font-bold">Total:</span>
              <span className="text-gold font-bold text-lg">R$ {order.total.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Buttons */}
      <div className="fixed bottom-0 left-0 right-0 bg-surface-00 border-t border-surface-02 px-4 py-4">
        <div className="flex gap-3">
          <Link
            to="/pedidos"
            className="flex-1 bg-gold hover:bg-gold/90 text-cream font-bold py-3 px-4 rounded-full transition-colors active:scale-95 text-center text-sm"
          >
            Meus Pedidos
          </Link>
          <Link
            to="/"
            className="flex-1 border-2 border-brand-mid text-parchment font-bold py-3 px-4 rounded-full transition-colors hover:border-slate-500 active:scale-95 text-center text-sm"
          >
            Cardápio
          </Link>
        </div>
      </div>
    </div>
  );
}
