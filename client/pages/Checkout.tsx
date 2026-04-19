import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronLeft, MapPin, Phone, User, Home, Tag, Loader2,
  CreditCard, Hash, Truck, Clock, Store, Check, AlertCircle,
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp } from "@/context/AppContext";
import { ordersApi, shippingApi, couponsApi, type CheckoutIn, type ApiShipping } from "@/lib/api";

type PaymentMethod = "pix" | "credit_card";
type DeliveryMode = "delivery" | "pickup";

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
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("pix");
  const [couponCode, setCouponCode] = useState("");
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [couponMsg, setCouponMsg] = useState("");
  const [couponApplied, setCouponApplied] = useState(false);

  const [shippingResult, setShippingResult] = useState<ApiShipping | null>(null);
  const [shippingLoading, setShippingLoading] = useState(false);

  const [errors, setErrors] = useState<Partial<typeof form>>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  // Pre-fill from logged-in customer
  useEffect(() => {
    if (customer) {
      setForm((prev) => ({
        ...prev,
        name: prev.name || customer.name,
        phone: prev.phone || (customer.phone ?? ""),
      }));
    }
  }, [customer]);

  // Recalculate shipping when address fields or mode change
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
          false,
        );
        setShippingResult(s);
      } catch { /* keep previous */ }
      finally { setShippingLoading(false); }
    }, 600);

    return () => clearTimeout(tid);
  }, [form.city, form.neighborhood, form.zip_code, cartSubtotal, deliveryMode]);

  if (cart.length === 0) {
    navigate("/");
    return null;
  }

  const deliveryFee = shippingResult?.shipping_price ?? 10.0;
  const shippingAvailable = shippingResult?.available !== false;
  const total = cartSubtotal + deliveryFee - couponDiscount;

  const validate = () => {
    const errs: Partial<typeof form> = {};
    if (!form.name.trim()) errs.name = "Nome obrigatório";
    if (!form.phone.trim()) errs.phone = "Telefone obrigatório";
    if (deliveryMode === "delivery") {
      if (!form.address.trim()) errs.address = "Endereço obrigatório";
      if (!form.city.trim()) errs.city = "Cidade obrigatória";
    }
    return errs;
  };

  const handleApplyCoupon = async () => {
    if (!couponCode.trim()) return;
    setCouponMsg("");
    try {
      const result = await couponsApi.apply(couponCode.trim(), cartSubtotal);
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
      setApiError(shippingResult?.message || "Região não atendida para delivery.");
      return;
    }
    const newErrors = validate();
    if (Object.keys(newErrors).length > 0) { setErrors(newErrors); return; }

    setLoading(true);
    setApiError("");

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
        complement: form.complement || undefined,
      },
      payment_method: paymentMethod,
      ...(couponApplied && couponCode ? { coupon_code: couponCode } : {}),
      ...(customer ? { customer_id: customer.id } : {}),
    };

    try {
      const order = await ordersApi.checkout(payload);
      clearCart();
      navigate(`/order-tracking?orderId=${order.id}`);
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "Erro ao criar pedido. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const shippingTypeLabel: Record<string, string> = {
    fixed: "Frete fixo",
    by_neighborhood: "Por bairro",
    by_cep_range: "Por CEP",
    by_distance: "Por distância",
    by_order_value: "Por valor do pedido",
    free: "Frete grátis",
    promotional: "Frete promocional",
    pickup: "Retirada no local",
    scheduled: "Entrega agendada",
    unavailable: "Região não atendida",
    blocked: "Região bloqueada",
    min_order: "Pedido mínimo",
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <div className="w-6" />
      </div>

      <div className="px-4 pt-6 pb-36 space-y-6">

        {/* Delivery Mode */}
        <div>
          <h2 className="text-cream font-bold text-lg mb-3 flex items-center gap-2">
            <Truck size={20} className="text-gold" />
            Tipo de entrega
          </h2>
          <div className="grid grid-cols-2 gap-2">
            {([
              { value: "delivery", label: "Delivery", icon: Truck },
              { value: "pickup", label: "Retirada", icon: Store },
            ] as { value: DeliveryMode; label: string; icon: typeof Truck }[]).map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setDeliveryMode(value)}
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
        </div>

        {/* Delivery Address */}
        {deliveryMode === "delivery" && (
          <div>
            <h2 className="text-cream font-bold text-lg mb-4 flex items-center gap-2">
              <MapPin size={20} className="text-gold" />
              {c.deliveryTitle}
            </h2>
            <div className="space-y-3">
              {/* Name */}
              <div>
                <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                  <User size={18} className="text-stone flex-shrink-0" />
                  <input type="text" placeholder={c.fields.name} value={form.name}
                    onChange={(e) => handleChange("name", e.target.value)}
                    className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
                </div>
                {errors.name && <p className="text-red-400 text-xs mt-1 ml-1">{errors.name}</p>}
              </div>

              {/* Phone */}
              <div>
                <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                  <Phone size={18} className="text-stone flex-shrink-0" />
                  <input type="tel" placeholder={c.fields.phone} value={form.phone}
                    onChange={(e) => handleChange("phone", e.target.value)}
                    className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
                </div>
                {errors.phone && <p className="text-red-400 text-xs mt-1 ml-1">{errors.phone}</p>}
              </div>

              {/* Address */}
              <div>
                <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                  <Home size={18} className="text-stone flex-shrink-0" />
                  <input type="text" placeholder={c.fields.address} value={form.address}
                    onChange={(e) => handleChange("address", e.target.value)}
                    className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
                </div>
                {errors.address && <p className="text-red-400 text-xs mt-1 ml-1">{errors.address}</p>}
              </div>

              {/* Neighborhood */}
              <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                <MapPin size={18} className="text-stone flex-shrink-0" />
                <input type="text" placeholder="Bairro" value={form.neighborhood}
                  onChange={(e) => handleChange("neighborhood", e.target.value)}
                  className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
              </div>

              {/* City */}
              <div>
                <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                  <MapPin size={18} className="text-stone flex-shrink-0" />
                  <input type="text" placeholder={c.fields.city} value={form.city}
                    onChange={(e) => handleChange("city", e.target.value)}
                    className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
                </div>
                {errors.city && <p className="text-red-400 text-xs mt-1 ml-1">{errors.city}</p>}
              </div>

              {/* ZIP */}
              <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                <Hash size={18} className="text-stone flex-shrink-0" />
                <input type="text" placeholder="CEP (opcional)" value={form.zip_code}
                  onChange={(e) => handleChange("zip_code", e.target.value)}
                  className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
              </div>

              {/* Complement */}
              <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                <Home size={18} className="text-stone flex-shrink-0" />
                <input type="text" placeholder={c.fields.complement} value={form.complement}
                  onChange={(e) => handleChange("complement", e.target.value)}
                  className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
              </div>
            </div>
          </div>
        )}

        {/* Pickup contact info */}
        {deliveryMode === "pickup" && (
          <div>
            <h2 className="text-cream font-bold text-lg mb-4 flex items-center gap-2">
              <User size={20} className="text-gold" />
              Seus dados
            </h2>
            <div className="space-y-3">
              <div>
                <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                  <User size={18} className="text-stone flex-shrink-0" />
                  <input type="text" placeholder="Seu nome" value={form.name}
                    onChange={(e) => handleChange("name", e.target.value)}
                    className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
                </div>
                {errors.name && <p className="text-red-400 text-xs mt-1 ml-1">{errors.name}</p>}
              </div>
              <div>
                <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
                  <Phone size={18} className="text-stone flex-shrink-0" />
                  <input type="tel" placeholder="Seu telefone" value={form.phone}
                    onChange={(e) => handleChange("phone", e.target.value)}
                    className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
                </div>
                {errors.phone && <p className="text-red-400 text-xs mt-1 ml-1">{errors.phone}</p>}
              </div>
            </div>
            <div className="mt-4 bg-gold/10 border border-gold/30 rounded-xl px-4 py-3 flex items-center gap-2">
              <Store size={16} className="text-gold flex-shrink-0" />
              <p className="text-parchment text-sm">Seu pedido estará pronto em até 15 minutos para retirada na loja.</p>
            </div>
          </div>
        )}

        {/* Shipping Result */}
        {shippingResult && (
          <div className={`rounded-xl px-4 py-3 flex items-start gap-3 ${
            !shippingResult.available
              ? "bg-red-500/10 border border-red-500/30"
              : shippingResult.free
              ? "bg-green-500/10 border border-green-500/30"
              : "bg-surface-02 border border-surface-03"
          }`}>
            {shippingLoading ? (
              <Loader2 size={16} className="text-stone animate-spin mt-0.5 flex-shrink-0" />
            ) : !shippingResult.available ? (
              <AlertCircle size={16} className="text-red-400 mt-0.5 flex-shrink-0" />
            ) : shippingResult.free ? (
              <Check size={16} className="text-green-400 mt-0.5 flex-shrink-0" />
            ) : (
              <Truck size={16} className="text-gold mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <p className={`text-sm font-medium ${!shippingResult.available ? "text-red-400" : shippingResult.free ? "text-green-400" : "text-cream"}`}>
                  {!shippingResult.available
                    ? shippingResult.message || "Região não atendida"
                    : shippingResult.free
                    ? shippingResult.message || "Frete grátis!"
                    : `R$ ${shippingResult.shipping_price.toFixed(2)}`}
                </p>
                {shippingResult.available && shippingResult.estimated_time > 0 && (
                  <div className="flex items-center gap-1 text-stone text-xs">
                    <Clock size={12} />
                    <span>{shippingResult.estimated_time} min</span>
                  </div>
                )}
              </div>
              {shippingResult.available && (
                <p className="text-stone text-xs mt-0.5">
                  {shippingTypeLabel[shippingResult.shipping_type] ?? shippingResult.shipping_type}
                  {shippingResult.rule_name && ` · ${shippingResult.rule_name}`}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Coupon */}
        <div>
          <h2 className="text-cream font-bold text-lg mb-3 flex items-center gap-2">
            <Tag size={20} className="text-gold" />
            Cupom de desconto
          </h2>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Código do cupom"
              value={couponCode}
              onChange={(e) => {
                setCouponCode(e.target.value.toUpperCase());
                setCouponApplied(false); setCouponMsg(""); setCouponDiscount(0);
              }}
              className="flex-1 bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/70 outline-none focus:border-gold text-sm uppercase"
            />
            <button onClick={handleApplyCoupon} className="px-4 py-3 bg-gold hover:bg-gold/90 rounded-xl text-cream font-bold text-sm transition-colors">
              Aplicar
            </button>
          </div>
          {couponMsg && (
            <p className={`text-xs mt-2 ml-1 ${couponApplied ? "text-green-400" : "text-red-400"}`}>{couponMsg}</p>
          )}
        </div>

        {/* Payment Method */}
        <div>
          <h2 className="text-cream font-bold text-lg mb-3 flex items-center gap-2">
            <CreditCard size={20} className="text-gold" />
            Forma de pagamento
          </h2>
          <div className="grid grid-cols-2 gap-2">
            {([
              { value: "pix", label: "PIX", icon: "🏦" },
              { value: "credit_card", label: "Cartão", icon: "💳" },
            ] as { value: PaymentMethod; label: string; icon: string }[]).map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPaymentMethod(opt.value)}
                className={`flex flex-col items-center gap-1 py-3 rounded-xl border text-sm font-medium transition-colors ${
                  paymentMethod === opt.value
                    ? "border-gold bg-gold/10 text-gold-light"
                    : "border-surface-03 bg-surface-02 text-stone hover:border-brand-mid"
                }`}
              >
                <span className="text-xl">{opt.icon}</span>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Order Summary */}
        <div>
          <h2 className="text-cream font-bold text-lg mb-4">{c.summaryTitle}</h2>
          <div className="space-y-3">
            {cart.map((item) => {
              const isMulti = item.flavorDivision > 1;
              const displayIcons = item.flavors.map((f) => f.icon).join("");
              const displayName = isMulti
                ? item.flavors.map((f) => f.name).join(" + ")
                : item.productData.name;
              return (
                <div key={item.cartItemId} className="bg-surface-02 rounded-xl p-4 flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-surface-03 flex-shrink-0 flex items-center justify-center text-lg">
                    {displayIcons || item.productData.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-cream font-semibold text-sm truncate">{displayName}</p>
                    <p className="text-stone text-xs">
                      {item.quantity}x · {item.selectedSize}
                      {isMulti && ` · ${item.flavorDivision === 2 ? "Meio a Meio" : "3 Sabores"}`}
                    </p>
                  </div>
                  <p className="text-gold font-bold text-sm flex-shrink-0">
                    R$ {(item.finalPrice * item.quantity).toFixed(2)}
                  </p>
                </div>
              );
            })}

            <div className="bg-surface-02 rounded-xl p-4 space-y-3 border border-surface-03">
              <div className="flex justify-between text-parchment text-sm">
                <span>Subtotal:</span>
                <span>R$ {cartSubtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-parchment text-sm">
                <span>Taxa de entrega:</span>
                <span className={shippingResult?.free ? "text-green-400" : ""}>
                  {shippingLoading
                    ? <Loader2 size={14} className="animate-spin inline" />
                    : shippingResult?.free
                    ? "Grátis"
                    : deliveryMode === "pickup"
                    ? "Grátis"
                    : `R$ ${deliveryFee.toFixed(2)}`}
                </span>
              </div>
              {shippingResult?.estimated_time && shippingResult.available && (
                <div className="flex justify-between text-stone text-xs">
                  <span className="flex items-center gap-1"><Clock size={12} /> Tempo estimado:</span>
                  <span>{shippingResult.estimated_time} min</span>
                </div>
              )}
              {couponDiscount > 0 && (
                <div className="flex justify-between text-green-400 text-sm">
                  <span>Desconto cupom:</span>
                  <span>-R$ {couponDiscount.toFixed(2)}</span>
                </div>
              )}
              <div className="border-t border-surface-03 pt-3 flex justify-between">
                <span className="text-cream font-bold">Total:</span>
                <span className="text-gold font-bold text-lg">R$ {Math.max(0, total).toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Region unavailable warning */}
        {shippingResult && !shippingResult.available && deliveryMode === "delivery" && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 flex gap-2">
            <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-400 text-sm font-medium">Região não atendida</p>
              <p className="text-red-300 text-xs mt-0.5">{shippingResult.message}</p>
              <p className="text-stone text-xs mt-1">Tente a opção de retirada no local, se disponível.</p>
            </div>
          </div>
        )}

        {apiError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3">
            <p className="text-red-400 text-sm text-center">{apiError}</p>
          </div>
        )}
      </div>

      {/* Confirm Button */}
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
    </div>
  );
}
