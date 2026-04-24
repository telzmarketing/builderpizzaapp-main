import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  Check,
  ChevronLeft,
  Clock,
  Hash,
  Home,
  Loader2,
  MapPin,
  Phone,
  Store,
  Tag,
  Truck,
  User,
  type LucideIcon,
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { checkoutTrackingPayload, trackEvent } from "@/lib/tracking";
import { useApp } from "@/context/AppContext";
import {
  couponsApi,
  ordersApi,
  paymentsApi,
  shippingApi,
  type ApiOrder,
  type ApiShipping,
  type CheckoutIn,
} from "@/lib/api";

type DeliveryMode = "delivery" | "pickup";
type PaymentState = "idle" | "loading" | "pending" | "approved" | "rejected" | "expired" | "error";

declare global {
  interface Window {
    MercadoPago?: new (publicKey: string, options?: Record<string, unknown>) => {
      bricks: () => {
        create: (
          type: string,
          containerId: string,
          settings: Record<string, unknown>
        ) => Promise<{ unmount: () => void }>;
      };
    };
  }
}

function statusClass(state: PaymentState): string {
  if (state === "approved") return "text-green-400";
  if (["rejected", "expired", "error"].includes(state)) return "text-red-400";
  return "text-stone";
}

export default function Checkout() {
  const navigate = useNavigate();
  const { cart, cartSubtotal, clearCart, siteContent, customer } = useApp();
  const c = siteContent.pages.checkout;

  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>("delivery");
  const [form, setForm] = useState({
    name: customer?.name ?? "",
    phone: customer?.phone ?? "",
    address: "",
    neighborhood: "",
    city: "",
    zip_code: "",
    complement: "",
  });
  const [couponCode, setCouponCode] = useState("");
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [couponMsg, setCouponMsg] = useState("");
  const [couponApplied, setCouponApplied] = useState(false);
  const [shippingResult, setShippingResult] = useState<ApiShipping | null>(null);
  const [shippingLoading, setShippingLoading] = useState(false);
  const [errors, setErrors] = useState<Partial<typeof form>>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");
  const [createdOrder, setCreatedOrder] = useState<ApiOrder | null>(null);
  const [paymentState, setPaymentState] = useState<PaymentState>("idle");
  const [paymentMessage, setPaymentMessage] = useState("");
  const brickController = useRef<{ unmount: () => void } | null>(null);

  useEffect(() => {
    if (!customer) return;
    setForm((prev) => ({
      ...prev,
      name: prev.name || customer.name,
      phone: prev.phone || (customer.phone ?? ""),
    }));
  }, [customer]);

  useEffect(() => {
    if (deliveryMode === "pickup") {
      setShippingResult({
        shipping_price: 0,
        shipping_type: "pickup",
        rule_name: "Retirada no local",
        free: true,
        estimated_time: 15,
        available: true,
        message: "",
      });
      return;
    }
    if (!form.city.trim() && !form.neighborhood.trim() && !form.zip_code.trim()) return;

    const tid = setTimeout(async () => {
      setShippingLoading(true);
      try {
        const s = await shippingApi.calculate(
          form.city,
          cartSubtotal,
          form.neighborhood || undefined,
          form.zip_code || undefined,
          false,
          false
        );
        setShippingResult(s);
      } catch {
        /* keep previous */
      } finally {
        setShippingLoading(false);
      }
    }, 600);
    return () => clearTimeout(tid);
  }, [form.city, form.neighborhood, form.zip_code, cartSubtotal, deliveryMode]);

  useEffect(() => {
    if (!createdOrder) return;
    let cancelled = false;

    async function loadScript() {
      if (window.MercadoPago) return;
      await new Promise<void>((resolve, reject) => {
        const existing = document.querySelector<HTMLScriptElement>("script[src='https://sdk.mercadopago.com/js/v2']");
        if (existing) {
          existing.addEventListener("load", () => resolve(), { once: true });
          existing.addEventListener("error", () => reject(new Error("Mercado Pago indisponivel.")), { once: true });
          return;
        }
        const script = document.createElement("script");
        script.src = "https://sdk.mercadopago.com/js/v2";
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Mercado Pago indisponivel."));
        document.head.appendChild(script);
      });
    }

    async function renderBrick() {
      setPaymentState("loading");
      setPaymentMessage("Carregando pagamento seguro...");
      try {
        const envKey = import.meta.env.VITE_MERCADO_PAGO_PUBLIC_KEY as string | undefined;
        const publicKey = envKey || (await paymentsApi.publicKey()).public_key;
        if (!publicKey) throw new Error("Chave publica do Mercado Pago nao configurada.");
        await loadScript();
        if (cancelled || !window.MercadoPago) return;
        if (brickController.current) brickController.current.unmount();

        const mp = new window.MercadoPago(publicKey, { locale: "pt-BR" });
        brickController.current = await mp.bricks().create("payment", "paymentBrick_container", {
          initialization: { amount: createdOrder.total },
          customization: {
            paymentMethods: {
              creditCard: "all",
              debitCard: "all",
              bankTransfer: "all",
              maxInstallments: 6,
            },
          },
          callbacks: {
            onReady: () => {
              setPaymentState("pending");
              setPaymentMessage("Aguardando pagamento.");
            },
            onSubmit: ({ formData }: { formData: Record<string, unknown> }) =>
              new Promise<void>(async (resolve, reject) => {
                try {
                  setPaymentState("loading");
                  setPaymentMessage("Processando pagamento...");
                  await paymentsApi.createFromBrick(createdOrder.id, formData);
                  setPaymentState("pending");
                  setPaymentMessage("Pagamento enviado. Aguardando confirmacao do Mercado Pago.");
                  resolve();
                } catch (err) {
                  setPaymentState("error");
                  setPaymentMessage(err instanceof Error ? err.message : "Erro ao processar pagamento.");
                  reject(err);
                }
              }),
            onError: () => {
              setPaymentState("error");
              setPaymentMessage("Erro ao carregar o Payment Brick.");
            },
          },
        });
      } catch (err) {
        setPaymentState("error");
        setPaymentMessage(err instanceof Error ? err.message : "Erro ao carregar pagamento.");
      }
    }

    renderBrick();
    return () => {
      cancelled = true;
      if (brickController.current) {
        brickController.current.unmount();
        brickController.current = null;
      }
    };
  }, [createdOrder]);

  useEffect(() => {
    if (!createdOrder) return;
    const id = setInterval(async () => {
      try {
        const status = await ordersApi.paymentStatus(createdOrder.id);
        if (status.payment_status === "approved" || status.pedido_status === "pago") {
          setPaymentState("approved");
          setPaymentMessage("Pagamento aprovado! Pedido enviado para preparo.");
          trackEvent("order_paid", createdOrder.total, { order_id: createdOrder.id });
          clearCart();
          clearInterval(id);
          setTimeout(() => navigate(`/order-tracking?orderId=${createdOrder.id}`), 1200);
        } else if (status.payment_status === "rejected" || status.pedido_status === "pagamento_recusado") {
          setPaymentState("rejected");
          setPaymentMessage("Pagamento recusado. Tente novamente com outro metodo.");
        } else if (["cancelled", "expired"].includes(status.payment_status) || status.pedido_status === "pagamento_expirado") {
          setPaymentState("expired");
          setPaymentMessage("Pagamento expirado ou cancelado. Tente novamente.");
        }
      } catch {
        /* keep polling */
      }
    }, 5000);
    return () => clearInterval(id);
  }, [createdOrder, clearCart, navigate]);

  if (cart.length === 0 && !createdOrder) {
    navigate("/");
    return null;
  }

  const deliveryFee = shippingResult?.shipping_price ?? 10.0;
  const shippingAvailable = shippingResult?.available !== false;
  const total = cartSubtotal + deliveryFee - couponDiscount;

  const handleChange = (field: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const validate = () => {
    const errs: Partial<typeof form> = {};
    if (!form.name.trim()) errs.name = "Nome obrigatorio";
    if (!form.phone.trim()) errs.phone = "Telefone obrigatorio";
    if (deliveryMode === "delivery") {
      if (!form.address.trim()) errs.address = "Endereco obrigatorio";
      if (!form.city.trim()) errs.city = "Cidade obrigatoria";
    }
    return errs;
  };

  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) return;
    setCouponMsg("");
    try {
      const result = await couponsApi.apply(couponCode.trim(), cartSubtotal, customer?.id, form.phone);
      if (result.valid) {
        setCouponDiscount(result.discount_amount);
        setCouponApplied(true);
        setCouponMsg(`Cupom aplicado! -R$ ${result.discount_amount.toFixed(2)}`);
      } else {
        setCouponDiscount(0);
        setCouponApplied(false);
        setCouponMsg(result.message);
      }
    } catch {
      setCouponMsg("Erro ao validar cupom.");
    }
  };

  const handleConfirm = async () => {
    if (!shippingAvailable && deliveryMode === "delivery") {
      setApiError(shippingResult?.message || "Regiao nao atendida para delivery.");
      return;
    }
    const newErrors = validate();
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    setApiError("");
    trackEvent("checkout_start", cartSubtotal);
    const tracking = checkoutTrackingPayload();
    const payload: CheckoutIn = {
      items: cart.map((item) => ({
        product_id: item.productId,
        quantity: item.quantity,
        selected_size: item.selectedSize,
        selected_size_id: item.selectedSizeId ?? null,
        flavor_division: item.flavorDivision,
        flavors: item.flavors.map((f) => ({
          product_id: f.productId,
          name: f.name,
          price: f.price,
          icon: f.icon,
        })),
        final_price: item.finalPrice,
        add_ons: item.selectedAddOns,
        selected_crust_type_id: item.selectedCrustType?.id ?? null,
        selected_crust_type_name: item.selectedCrustType?.name ?? null,
        selected_drink_variant_id: item.selectedDrinkVariant?.id ?? null,
        selected_drink_variant_name: item.selectedDrinkVariant?.name ?? null,
        notes: item.notes ?? null,
      })),
      delivery: {
        name: form.name,
        phone: form.phone,
        street: deliveryMode === "pickup" ? "Retirada no local" : form.address,
        city: form.city || "Retirada",
        neighborhood: deliveryMode === "pickup" ? undefined : form.neighborhood || undefined,
        zip_code: deliveryMode === "pickup" ? undefined : form.zip_code || undefined,
        complement: form.complement || undefined,
        is_pickup: deliveryMode === "pickup",
        is_scheduled: false,
      },
      payment_method: "pix",
      ...tracking,
      ...(couponApplied && couponCode ? { coupon_code: couponCode } : {}),
      ...(customer ? { customer_id: customer.id } : {}),
    };

    try {
      const order = await ordersApi.checkout(payload);
      trackEvent("order_created", order.total, { order_id: order.id });
      setCreatedOrder(order);
      setPaymentState("pending");
      setPaymentMessage("Pedido criado. Conclua o pagamento abaixo.");
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    } catch (err) {
      setApiError(err instanceof Error ? err.message : "Erro ao criar pedido. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
        <div className="w-6" />
      </div>

      <div className="px-4 pt-6 pb-36 space-y-6">
        <section>
          <h2 className="text-cream font-bold text-lg mb-3 flex items-center gap-2">
            <Truck size={20} className="text-gold" />
            Tipo de entrega
          </h2>
          <div className="grid grid-cols-2 gap-2">
            {([
              { value: "delivery", label: "Delivery", icon: Truck },
              { value: "pickup", label: "Retirada", icon: Store },
            ] as { value: DeliveryMode; label: string; icon: LucideIcon }[]).map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setDeliveryMode(value)}
                disabled={!!createdOrder}
                className={`flex flex-col items-center gap-1 py-3 rounded-xl border text-sm font-medium transition-colors ${
                  deliveryMode === value
                    ? "border-gold bg-gold/10 text-gold-light"
                    : "border-surface-03 bg-surface-02 text-stone hover:border-brand-mid"
                }`}
              >
                <Icon size={18} />
                {label}
              </button>
            ))}
          </div>
        </section>

        <section>
          <h2 className="text-cream font-bold text-lg mb-4 flex items-center gap-2">
            {deliveryMode === "delivery" ? <MapPin size={20} className="text-gold" /> : <User size={20} className="text-gold" />}
            {deliveryMode === "delivery" ? c.deliveryTitle : "Seus dados"}
          </h2>
          <div className="space-y-3">
            <Field icon={User} placeholder={c.fields.name} value={form.name} disabled={!!createdOrder} onChange={(v) => handleChange("name", v)} error={errors.name} />
            <Field icon={Phone} placeholder={c.fields.phone} value={form.phone} disabled={!!createdOrder} onChange={(v) => handleChange("phone", v)} error={errors.phone} />
            {deliveryMode === "delivery" && (
              <>
                <Field icon={Home} placeholder={c.fields.address} value={form.address} disabled={!!createdOrder} onChange={(v) => handleChange("address", v)} error={errors.address} />
                <Field icon={MapPin} placeholder="Bairro" value={form.neighborhood} disabled={!!createdOrder} onChange={(v) => handleChange("neighborhood", v)} />
                <Field icon={MapPin} placeholder={c.fields.city} value={form.city} disabled={!!createdOrder} onChange={(v) => handleChange("city", v)} error={errors.city} />
                <Field icon={Hash} placeholder="CEP (opcional)" value={form.zip_code} disabled={!!createdOrder} onChange={(v) => handleChange("zip_code", v)} />
                <Field icon={Home} placeholder={c.fields.complement} value={form.complement} disabled={!!createdOrder} onChange={(v) => handleChange("complement", v)} />
              </>
            )}
          </div>
        </section>

        {shippingResult && (
          <div className={`rounded-xl px-4 py-3 flex items-start gap-3 ${
            !shippingResult.available
              ? "bg-red-500/10 border border-red-500/30"
              : shippingResult.free
              ? "bg-green-500/10 border border-green-500/30"
              : "bg-surface-02 border border-surface-03"
          }`}>
            {shippingLoading ? <Loader2 size={16} className="text-stone animate-spin mt-0.5 flex-shrink-0" /> : !shippingResult.available ? <AlertCircle size={16} className="text-red-400 mt-0.5 flex-shrink-0" /> : <Check size={16} className="text-green-400 mt-0.5 flex-shrink-0" />}
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <p className={`text-sm font-medium ${!shippingResult.available ? "text-red-400" : shippingResult.free ? "text-green-400" : "text-cream"}`}>
                  {!shippingResult.available ? shippingResult.message || "Regiao nao atendida" : shippingResult.free ? "Frete gratis" : `R$ ${shippingResult.shipping_price.toFixed(2)}`}
                </p>
                {shippingResult.available && shippingResult.estimated_time > 0 && (
                  <div className="flex items-center gap-1 text-stone text-xs">
                    <Clock size={12} />
                    <span>{shippingResult.estimated_time} min</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {!createdOrder && (
          <section>
            <h2 className="text-cream font-bold text-lg mb-3 flex items-center gap-2">
              <Tag size={20} className="text-gold" />
              Cupom de desconto
            </h2>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Codigo do cupom"
                value={couponCode}
                onChange={(e) => {
                  setCouponCode(e.target.value.toUpperCase());
                  setCouponApplied(false);
                  setCouponMsg("");
                  setCouponDiscount(0);
                }}
                className="flex-1 bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/70 outline-none focus:border-gold text-sm uppercase"
              />
              <button onClick={handleApplyCoupon} className="px-4 py-3 bg-gold hover:bg-gold/90 rounded-xl text-cream font-bold text-sm transition-colors">
                Aplicar
              </button>
            </div>
            {couponMsg && <p className={`text-xs mt-2 ml-1 ${couponApplied ? "text-green-400" : "text-red-400"}`}>{couponMsg}</p>}
          </section>
        )}

        <section>
          <h2 className="text-cream font-bold text-lg mb-4">{c.summaryTitle}</h2>
          <div className="space-y-3">
            {cart.map((item) => {
              const isMulti = item.flavorDivision > 1;
              const displayIcons = item.flavors.map((f) => f.icon).join("");
              const displayName = isMulti ? item.flavors.map((f) => f.name).join(" + ") : item.productData.name;
              return (
                <div key={item.cartItemId} className="bg-surface-02 rounded-xl p-4 flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-surface-03 flex-shrink-0 flex items-center justify-center text-lg">
                    {displayIcons || item.productData.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-cream font-semibold text-sm truncate">{displayName}</p>
                    <p className="text-stone text-xs">{item.quantity}x - {item.selectedSize}</p>
                  </div>
                  <p className="text-gold font-bold text-sm flex-shrink-0">R$ {(item.finalPrice * item.quantity).toFixed(2)}</p>
                </div>
              );
            })}

            <div className="bg-surface-02 rounded-xl p-4 space-y-3 border border-surface-03">
              <Line label="Subtotal:" value={`R$ ${cartSubtotal.toFixed(2)}`} />
              <Line label="Taxa de entrega:" value={deliveryMode === "pickup" || shippingResult?.free ? "Gratis" : `R$ ${deliveryFee.toFixed(2)}`} />
              {couponDiscount > 0 && <Line label="Desconto cupom:" value={`-R$ ${couponDiscount.toFixed(2)}`} good />}
              <div className="border-t border-surface-03 pt-3 flex justify-between">
                <span className="text-cream font-bold">Total:</span>
                <span className="text-gold font-bold text-lg">R$ {Math.max(0, total).toFixed(2)}</span>
              </div>
            </div>
          </div>
        </section>

        {createdOrder && (
          <section className="bg-surface-02 rounded-xl p-4 border border-surface-03">
            <h2 className="text-cream font-bold text-lg mb-3">Pagamento Mercado Pago</h2>
            <p className={`text-sm mb-3 ${statusClass(paymentState)}`}>{paymentMessage || "Aguardando pagamento."}</p>
            <div id="paymentBrick_container" className={paymentState === "approved" ? "hidden" : ""} />
            {paymentState === "loading" && (
              <div className="flex items-center justify-center py-4 text-stone gap-2">
                <Loader2 size={18} className="animate-spin" />
                Processando...
              </div>
            )}
          </section>
        )}

        {apiError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3">
            <p className="text-red-400 text-sm text-center">{apiError}</p>
          </div>
        )}
      </div>

      {!createdOrder && (
        <div className="fixed bottom-0 left-0 right-0 bg-surface-00 border-t border-surface-02 px-4 py-4">
          <button
            onClick={handleConfirm}
            disabled={loading || (!shippingAvailable && deliveryMode === "delivery")}
            className="w-full bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold py-4 px-4 rounded-full text-center transition-colors text-lg active:scale-95 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 size={20} className="animate-spin" />}
            {loading ? "Processando..." : c.confirmButton}
          </button>
        </div>
      )}
    </div>
  );
}

function Field({
  icon: Icon,
  placeholder,
  value,
  disabled,
  onChange,
  error,
}: {
  icon: LucideIcon;
  placeholder: string;
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  error?: string;
}) {
  return (
    <div>
      <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
        <Icon size={18} className="text-stone flex-shrink-0" />
        <input
          type="text"
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm disabled:opacity-60"
        />
      </div>
      {error && <p className="text-red-400 text-xs mt-1 ml-1">{error}</p>}
    </div>
  );
}

function Line({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className={`flex justify-between text-sm ${good ? "text-green-400" : "text-parchment"}`}>
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
