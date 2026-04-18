import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronLeft, MapPin, Phone, User, Home, Tag, Loader2, CreditCard } from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp } from "@/context/AppContext";
import { ordersApi, shippingApi, couponsApi, type CheckoutIn } from "@/lib/api";

type PaymentMethod = "pix" | "credit_card";

export default function Checkout() {
  const navigate = useNavigate();
  const { cart, cartSubtotal, clearCart, siteContent, customer } = useApp();
  const c = siteContent.pages.checkout;

  const [form, setForm] = useState({
    name: customer?.name ?? "",
    phone: customer?.phone ?? "",
    address: "",
    city: "",
    complement: "",
  });
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("pix");
  const [couponCode, setCouponCode] = useState("");
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [couponMsg, setCouponMsg] = useState("");
  const [couponApplied, setCouponApplied] = useState(false);

  const [deliveryFee, setDeliveryFee] = useState(10.0);
  const [shippingFree, setShippingFree] = useState(false);

  const [errors, setErrors] = useState<Partial<typeof form>>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  // Pre-fill form from logged-in customer
  useEffect(() => {
    if (customer) {
      setForm((prev) => ({
        ...prev,
        name: prev.name || customer.name,
        phone: prev.phone || (customer.phone ?? ""),
      }));
    }
  }, [customer]);

  // Calculate shipping when city changes
  useEffect(() => {
    if (!form.city.trim()) return;
    shippingApi.calculate(form.city, cartSubtotal).then((s) => {
      setDeliveryFee(s.shipping_price);
      setShippingFree(s.free);
    }).catch(() => { /* keep default */ });
  }, [form.city, cartSubtotal]);

  if (cart.length === 0) {
    navigate("/");
    return null;
  }

  const total = cartSubtotal + deliveryFee - couponDiscount;

  const validate = () => {
    const newErrors: Partial<typeof form> = {};
    if (!form.name.trim()) newErrors.name = "Nome obrigatório";
    if (!form.phone.trim()) newErrors.phone = "Telefone obrigatório";
    if (!form.address.trim()) newErrors.address = "Endereço obrigatório";
    if (!form.city.trim()) newErrors.city = "Cidade obrigatória";
    return newErrors;
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
    const newErrors = validate();
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    setApiError("");

    const payload: CheckoutIn = {
      items: cart.map((item) => ({
        product_id: item.productId,
        quantity: item.quantity,
        selected_size: item.selectedSize,
        flavor_division: item.flavorDivision,
        flavors: item.flavors.map((f) => ({
          product_id: f.productId,
          name: f.name,
          price: f.price,
          icon: f.icon,
        })),
        final_price: item.finalPrice,
        add_ons: item.selectedAddOns,
      })),
      delivery: {
        name: form.name,
        phone: form.phone,
        street: form.address,
        city: form.city,
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
        {/* Delivery Address */}
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

            {/* Complement */}
            <div className="flex items-center gap-3 bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 focus-within:border-gold transition-colors">
              <Home size={18} className="text-stone flex-shrink-0" />
              <input type="text" placeholder={c.fields.complement} value={form.complement}
                onChange={(e) => handleChange("complement", e.target.value)}
                className="flex-1 bg-transparent text-cream placeholder-stone/70 outline-none text-sm" />
            </div>
          </div>
        </div>

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
              onChange={(e) => { setCouponCode(e.target.value.toUpperCase()); setCouponApplied(false); setCouponMsg(""); setCouponDiscount(0); }}
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
                className={`flex flex-col items-center gap-1 py-3 rounded-xl border text-sm font-medium transition-colors ${paymentMethod === opt.value ? "border-gold bg-gold/10 text-gold-light" : "border-surface-03 bg-surface-02 text-stone hover:border-brand-mid"}`}
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
                <span className={shippingFree ? "text-green-400" : ""}>
                  {shippingFree ? "Grátis" : `R$ ${deliveryFee.toFixed(2)}`}
                </span>
              </div>
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
          disabled={loading}
          className="w-full bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold py-4 px-4 rounded-full text-center transition-colors text-lg active:scale-95 flex items-center justify-center gap-2"
        >
          {loading && <Loader2 size={20} className="animate-spin" />}
          {loading ? "Processando..." : c.confirmButton}
        </button>
      </div>
    </div>
  );
}
