import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  Banknote,
  Check,
  ChevronLeft,
  Clock,
  Copy,
  CreditCard,
  Hash,
  Home,
  Loader2,
  MapPin,
  Phone,
  QrCode,
  Store,
  Tag,
  Truck,
  User,
  type LucideIcon,
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { checkoutTrackingPayload, trackEvent, getTrackingData, firePixelEvent } from "@/lib/tracking";
import { pizzaSizeLabel } from "@/lib/pizzaSizes";
import { useApp } from "@/context/AppContext";
import {
  couponsApi,
  customersApi,
  customerEventsApi,
  ordersApi,
  paymentsApi,
  shippingApi,
  storeOperationApi,
  isAssetUrl,
  resolveAssetUrl,
  type ApiAddress,
  type ApiCouponGift,
  type ApiOrder,
  type ApiPayment,
  type ApiPaymentMethods,
  type ApiShipping,
  type CheckoutIn,
  type StoreOperationStatus,
} from "@/lib/api";

type DeliveryMode = "delivery" | "pickup";
type SelectedPaymentMethod = "pix" | "card" | "delivery";
type DeliveryPaymentMethod = "card" | "cash";
type PaymentState = "idle" | "loading" | "pending" | "approved" | "rejected" | "expired" | "error";

declare global {
  interface Window {
    MercadoPago?: new (publicKey: string, options?: Record<string, unknown>) => {
      createCardToken: (data: Record<string, string>) => Promise<{ id: string }>;
      getPaymentMethods: (data: { bin: string }) => Promise<{ results: Array<{ id: string; payment_type_id: string }> }>;
    };
  }
}

function formatCardNumber(v: string) {
  return v.replace(/\D/g, "").slice(0, 16).replace(/(.{4})/g, "$1 ").trim();
}
function formatExpiry(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 4);
  return d.length >= 3 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
}
function formatCpf(v: string) {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 3) return d;
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`;
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`;
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`;
}

// sessionStorage key that persists the locked order across page refreshes and back-navigation
const LOCKED_ORDER_KEY = "mo_locked_order_id";

function statusClass(state: PaymentState): string {
  if (state === "approved") return "text-green-400";
  if (["rejected", "expired", "error"].includes(state)) return "text-red-400";
  return "text-stone";
}

export default function Checkout() {
  const navigate = useNavigate();
  const { cart, cartSubtotal, clearCart, siteContent, customer, customerLogout } = useApp();
  const c = siteContent.pages.checkout;

  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>("delivery");
  const [selectedAddressId, setSelectedAddressId] = useState<string | "new" | null>(null);
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
  const [couponFreeShipping, setCouponFreeShipping] = useState(false);
  const [couponGift, setCouponGift] = useState<ApiCouponGift | null>(null);
  const [couponMsg, setCouponMsg] = useState("");
  const [couponApplied, setCouponApplied] = useState(false);
  const [shippingResult, setShippingResult] = useState<ApiShipping | null>(null);
  const [shippingLoading, setShippingLoading] = useState(false);
  const [errors, setErrors] = useState<Partial<typeof form>>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");
  const [createdOrder, setCreatedOrder] = useState<ApiOrder | null>(null);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<SelectedPaymentMethod>("pix");
  const [deliveryPaymentMethod, setDeliveryPaymentMethod] = useState<DeliveryPaymentMethod>("card");
  const [cashNeedsChange, setCashNeedsChange] = useState(false);
  const [cashChangeFor, setCashChangeFor] = useState("");
  const [paymentMethods, setPaymentMethods] = useState<ApiPaymentMethods | null>(null);
  const [payment, setPayment] = useState<ApiPayment | null>(null);
  const [paymentState, setPaymentState] = useState<PaymentState>("idle");
  const [paymentMessage, setPaymentMessage] = useState("");
  const [storeStatus, setStoreStatus] = useState<StoreOperationStatus | null>(null);
  const [scheduledFor, setScheduledFor] = useState("");
  const [checkoutAddresses, setCheckoutAddresses] = useState<ApiAddress[] | null>(null);
  const [cardNumber, setCardNumber] = useState("");
  const [cardName, setCardName] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvv, setCardCvv] = useState("");
  const [cardCpf, setCardCpf] = useState("");
  const [cardFunction, setCardFunction] = useState<"credit" | "debit">("credit");
  const [cardSubmitting, setCardSubmitting] = useState(false);
  const [cardError, setCardError] = useState("");
  const [pixExpiresAt, setPixExpiresAt] = useState<number | null>(null);
  const [pixSecondsLeft, setPixSecondsLeft] = useState<number | null>(null);
  const paymentMethodsRef = useRef<ApiPaymentMethods | null>(null);

  // Guard: if a payment was already initiated for a previous session, redirect to order tracking immediately.
  useEffect(() => {
    const lockedId = sessionStorage.getItem(LOCKED_ORDER_KEY);
    if (!lockedId) return;
    let cancelled = false;
    ordersApi.paymentStatus(lockedId).then((status) => {
      if (cancelled) return;
      if (status.checkout_locked) {
        navigate(`/order-tracking?orderId=${lockedId}`, { replace: true });
      } else {
        sessionStorage.removeItem(LOCKED_ORDER_KEY);
      }
    }).catch(() => { if (!cancelled) sessionStorage.removeItem(LOCKED_ORDER_KEY); });
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Intercept browser back-button once an order has been created and payment initiated.
  useEffect(() => {
    if (!createdOrder) return;
    // Push an extra history entry so the first "back" press lands here and we can intercept it.
    window.history.pushState({ moCheckoutLocked: true }, "");
    const handlePop = () => {
      navigate(`/order-tracking?orderId=${createdOrder.id}`, { replace: true });
    };
    window.addEventListener("popstate", handlePop);
    return () => window.removeEventListener("popstate", handlePop);
  }, [createdOrder?.id, navigate]);

  const savedAddresses = checkoutAddresses ?? customer?.addresses ?? [];
  const savedAddressSignature = savedAddresses
    .map((addr) => [
      addr.id,
      addr.is_default,
      addr.street,
      addr.number ?? "",
      addr.neighborhood ?? "",
      addr.city,
      addr.zip_code ?? "",
      addr.complement ?? "",
    ].join(":"))
    .join("|");

  const applyAddress = (addrId: string | "new") => {
    setSelectedAddressId(addrId);
    if (addrId === "new") {
      setForm((prev) => ({ ...prev, address: "", neighborhood: "", city: "", zip_code: "", complement: "" }));
      return;
    }
    const addr = savedAddresses.find((a) => a.id === addrId);
    if (addr) {
      setForm((prev) => ({
        ...prev,
        address: `${addr.street}${addr.number ? `, ${addr.number}` : ""}`,
        neighborhood: addr.neighborhood || "",
        city: addr.city,
        zip_code: addr.zip_code || "",
        complement: addr.complement || "",
      }));
    }
  };

  useEffect(() => {
    if (!customer) return;
    setForm((prev) => ({
      ...prev,
      name: prev.name || customer.name,
      phone: prev.phone || (customer.phone ?? ""),
    }));
  }, [customer?.id, customer?.name, customer?.phone]);

  useEffect(() => {
    if (!customer?.id) {
      setCheckoutAddresses(null);
      setSelectedAddressId(null);
      return;
    }

    let cancelled = false;
    setCheckoutAddresses(customer.addresses ?? []);
    customersApi.listAddresses(customer.id)
      .then((addresses) => {
        if (!cancelled) setCheckoutAddresses(addresses);
      })
      .catch(() => {
        if (!cancelled) setCheckoutAddresses(customer.addresses ?? []);
      });

    return () => {
      cancelled = true;
    };
  }, [customer?.id]);

  useEffect(() => {
    if (!customer || deliveryMode !== "delivery" || savedAddresses.length === 0) return;
    if (selectedAddressId === "new") return;

    const selectedStillExists = selectedAddressId
      ? savedAddresses.some((addr) => addr.id === selectedAddressId)
      : false;
    const def = savedAddresses.find((addr) => addr.is_default) ?? savedAddresses[0];
    applyAddress(selectedStillExists && selectedAddressId ? selectedAddressId : def.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customer?.id, deliveryMode, selectedAddressId, savedAddressSignature]);

  useEffect(() => {
    const td = getTrackingData();
    customerEventsApi.register({
      event_type: "checkout_started",
      event_name: "Iniciou checkout",
      customer_id: customer?.id ?? null,
      session_id: td.session_id,
      page_url: window.location.href,
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    storeOperationApi.status().then(setStoreStatus).catch(() => setStoreStatus(null));
    paymentsApi.methods().then((methods) => {
      setPaymentMethods(methods);
      paymentMethodsRef.current = methods;
      if (!methods.accept_pix && (methods.accept_credit_card || methods.accept_debit_card)) {
        setSelectedPaymentMethod("card");
      } else if (!methods.accept_pix && !methods.accept_credit_card && !methods.accept_debit_card && methods.accept_cash) {
        setSelectedPaymentMethod("delivery");
      }
    }).catch(() => setPaymentMethods(null));
  }, []);

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
    if (selectedPaymentMethod === "delivery") return;
    const deadline = Date.now() + 30 * 60 * 1000; // 30 min
    const id = setInterval(async () => {
      if (Date.now() > deadline) {
        clearInterval(id);
        sessionStorage.removeItem(LOCKED_ORDER_KEY);
        setPaymentState("expired");
        setPaymentMessage("Tempo de pagamento esgotado. Tente novamente.");
        return;
      }
      try {
        const status = await ordersApi.paymentStatus(createdOrder.id);
        if (status.qr_code || status.qr_code_text || status.payment_url) {
          setPayment((prev) => prev ? {
            ...prev,
            qr_code: status.qr_code ?? prev.qr_code,
            qr_code_text: status.qr_code_text ?? prev.qr_code_text,
            payment_url: status.payment_url ?? prev.payment_url,
          } : prev);
        }
        if (
          status.payment_status === "approved" ||
          status.payment_status === "paid" ||
          status.pedido_status === "pago" ||
          status.pedido_status === "paid"
        ) {
          setPaymentState("approved");
          setPaymentMessage("Pagamento aprovado! Pedido enviado para preparo.");
          trackEvent("order_paid", createdOrder.total, { order_id: createdOrder.id });
          firePixelEvent("Purchase", { value: createdOrder.total, order_id: createdOrder.id });
          const _tdPaid = getTrackingData();
          customerEventsApi.register({
            event_type: "order_paid",
            event_name: "Pagamento confirmado",
            order_id: createdOrder.id,
            customer_id: customer?.id ?? null,
            session_id: _tdPaid.session_id,
          }).catch(() => {});
          clearCart();
          sessionStorage.removeItem(LOCKED_ORDER_KEY);
          clearInterval(id);
          setTimeout(() => navigate(`/order-tracking?orderId=${createdOrder.id}`), 1200);
        } else if (status.payment_status === "rejected" || status.pedido_status === "pagamento_recusado") {
          sessionStorage.removeItem(LOCKED_ORDER_KEY);
          setPaymentState("rejected");
          setPaymentMessage("Pagamento recusado. Tente novamente com outro metodo.");
          clearInterval(id);
        } else if (["cancelled", "expired"].includes(status.payment_status) || status.pedido_status === "pagamento_expirado") {
          sessionStorage.removeItem(LOCKED_ORDER_KEY);
          setPaymentState("expired");
          setPaymentMessage("Pagamento expirado ou cancelado. Tente novamente.");
          clearCart();
          clearInterval(id);
        }
      } catch {
        /* keep polling */
      }
    }, 8000);
    return () => clearInterval(id);
  }, [createdOrder, selectedPaymentMethod, clearCart, navigate]);

  // Countdown do PIX (30 min = 1800s)
  useEffect(() => {
    if (!pixExpiresAt) return;
    const tick = () => {
      const left = Math.max(0, Math.round((pixExpiresAt - Date.now()) / 1000));
      setPixSecondsLeft(left);
      if (left === 0) {
        setPaymentState("expired");
        setPaymentMessage("PIX expirado. Gere um novo PIX, mude a forma de pagamento ou cancele o pedido.");
        clearCart();
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [pixExpiresAt, clearCart]);

  const promotionBlocksCoupons = cart.some((item) => item.promotionApplied && item.promotionBlocksOtherCoupons);
  const promotionFreeShipping = cart.some((item) => item.promotionApplied && item.promotionFreeShipping);
  const promotionGifts = useMemo<ApiCouponGift[]>(() => {
    const gifts = new Map<string, ApiCouponGift>();
    cart.forEach((item) => {
      if (!item.promotionApplied || !item.promotionGiftEnabled || !item.promotionGiftProductId || !item.promotionGiftName) return;
      const key = `${item.promotionId ?? "promotion"}-${item.promotionGiftProductId}`;
      const quantity = Math.max(1, item.promotionGiftQuantity ?? 1) * item.quantity;
      const current = gifts.get(key);
      if (current) {
        current.quantity += quantity;
        return;
      }
      gifts.set(key, {
        product_id: item.promotionGiftProductId,
        name: item.promotionGiftName,
        icon: item.promotionGiftIcon ?? "🎁",
        quantity,
        unit_price: 0,
        original_price: 0,
        is_gift: true,
        gift_reason: "product_promotion",
        promotion_id: item.promotionId ?? null,
        promotion_name: item.promotionName ?? null,
      });
    });
    return Array.from(gifts.values());
  }, [cart]);

  useEffect(() => {
    if (!promotionBlocksCoupons || !couponApplied) return;
    setCouponCode("");
    setCouponDiscount(0);
    setCouponFreeShipping(false);
    setCouponGift(null);
    setCouponApplied(false);
    setCouponMsg("Este carrinho tem produto em promocao que bloqueia outros cupons.");
  }, [promotionBlocksCoupons, couponApplied]);

  if (!customer && !createdOrder) {
    navigate("/conta?redirect=/checkout", { replace: true });
    return null;
  }

  if (cart.length === 0 && !createdOrder) {
    navigate("/");
    return null;
  }

  const deliveryFee = shippingResult?.shipping_price ?? 10.0;
  const shippingAvailable = shippingResult?.available !== false;
  const deliveryFeeFinal = couponFreeShipping || promotionFreeShipping || deliveryMode === "pickup" || shippingResult?.free ? 0 : deliveryFee;
  const total = cartSubtotal + deliveryFeeFinal - couponDiscount;

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
    if (promotionBlocksCoupons) {
      setCouponMsg("Este carrinho tem produto em promocao que bloqueia outros cupons.");
      return;
    }
    setCouponMsg("");
    try {
      const result = await couponsApi.apply(couponCode.trim(), cartSubtotal, customer?.id, form.phone, deliveryFee);
      if (result.valid) {
        setCouponDiscount(result.discount_amount);
        setCouponFreeShipping(result.free_shipping_applied);
        setCouponGift(result.gift);
        setCouponApplied(true);
        setCouponMsg(result.message);
      } else {
        setCouponDiscount(0);
        setCouponFreeShipping(false);
        setCouponGift(null);
        setCouponApplied(false);
        setCouponMsg(result.message);
      }
    } catch {
      setCouponMsg("Erro ao validar cupom.");
    }
  };

  const handleRemoveCoupon = () => {
    setCouponCode("");
    setCouponApplied(false);
    setCouponMsg("");
    setCouponDiscount(0);
    setCouponFreeShipping(false);
    setCouponGift(null);
  };

  const handleConfirm = async () => {
    const mustSchedule = !!storeStatus && !storeStatus.is_open && storeStatus.allow_scheduled_orders;
    if (storeStatus && !storeStatus.is_open && !storeStatus.allow_scheduled_orders) {
      setApiError(storeStatus.message || "Loja fechada no momento.");
      return;
    }
    if (mustSchedule && !scheduledFor) {
      setApiError("Escolha um horario futuro disponivel para agendar o pedido.");
      return;
    }
    if (!shippingAvailable && deliveryMode === "delivery") {
      setApiError(shippingResult?.message || "Regiao nao atendida para delivery.");
      return;
    }
    if (paymentMethods) {
      const pixDisabled = selectedPaymentMethod === "pix" && !paymentMethods.accept_pix;
      const cardDisabled = selectedPaymentMethod === "card" && !paymentMethods.accept_credit_card && !paymentMethods.accept_debit_card;
      const deliveryDisabled = selectedPaymentMethod === "delivery" && !paymentMethods.accept_cash;
      if (pixDisabled || cardDisabled || deliveryDisabled) {
        setApiError("Forma de pagamento indisponivel no momento.");
        return;
      }
    }
    if (selectedPaymentMethod === "delivery" && deliveryPaymentMethod === "cash" && cashNeedsChange) {
      const changeFor = Number(cashChangeFor.replace(",", "."));
      if (!Number.isFinite(changeFor) || changeFor <= total) {
        setApiError("Informe um valor de troco maior que o total do pedido.");
        return;
      }
    }
    const newErrors = validate();
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    setApiError("");
    trackEvent("checkout_start", cartSubtotal);
    firePixelEvent("InitiateCheckout", { value: cartSubtotal });
    const tracking = checkoutTrackingPayload();
    const changeFor = Number(cashChangeFor.replace(",", "."));
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
        is_scheduled: mustSchedule,
        scheduled_for: mustSchedule ? new Date(scheduledFor).toISOString() : null,
      },
      payment_method: selectedPaymentMethod === "pix"
        ? "pix"
        : selectedPaymentMethod === "card"
          ? "credit_card"
          : "pay_on_delivery",
      ...(selectedPaymentMethod === "delivery" ? {
        delivery_payment_method: deliveryPaymentMethod,
        cash_needs_change: deliveryPaymentMethod === "cash" ? cashNeedsChange : null,
        cash_change_for: deliveryPaymentMethod === "cash" && cashNeedsChange ? changeFor : null,
      } : {}),
      ...tracking,
      ...(couponApplied && couponCode && !promotionBlocksCoupons ? { coupon_code: couponCode } : {}),
      ...(customer ? { customer_id: customer.id } : {}),
    };

    try {
      const order = await ordersApi.checkout(payload);
      trackEvent("order_created", order.total, { order_id: order.id });
      const _td = getTrackingData();
      customerEventsApi.register({
        event_type: "order_created",
        event_name: "Pedido criado",
        order_id: order.id,
        customer_id: customer?.id ?? null,
        session_id: _td.session_id,
      }).catch(() => {});
      setCreatedOrder(order);
      setPayment(null);
      if (selectedPaymentMethod === "pix") {
        sessionStorage.setItem(LOCKED_ORDER_KEY, order.id);
        setPaymentState("loading");
        setPaymentMessage("Gerando PIX seguro...");
        const pixPayment = await paymentsApi.createPix(order.id, order.total);
        setPayment(pixPayment);
        setPixExpiresAt(Date.now() + 30 * 60 * 1000); // 30 min de validade
        setPaymentState("pending");
        setPaymentMessage(
          pixPayment.qr_code_text
            ? "PIX gerado. Pague pelo QR Code ou copia-e-cola."
            : "PIX criado. Aguardando retorno do QR Code do Mercado Pago.",
        );
      } else {
        if (selectedPaymentMethod === "card") {
          sessionStorage.setItem(LOCKED_ORDER_KEY, order.id);
          setPaymentState("pending");
          setPaymentMessage("Preencha os dados do cartao para concluir.");
        } else {
          sessionStorage.removeItem(LOCKED_ORDER_KEY);
          clearCart();
          setPaymentState("pending");
          setPaymentMessage("Pedido recebido. O pagamento sera feito na entrega.");
          setTimeout(() => navigate(`/order-tracking?orderId=${order.id}`), 1200);
        }
      }
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro ao criar pedido. Tente novamente.";
      if (msg.includes("Conta não encontrada") || msg.includes("CustomerNotFound")) {
        customerLogout();
        navigate("/conta?redirect=/checkout", { replace: true });
        return;
      }
      setApiError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleCardPay = async () => {
    if (!createdOrder) return;
    setCardError("");
    setCardSubmitting(true);
    try {
      if (!window.MercadoPago) {
        await new Promise<void>((resolve, reject) => {
          const existing = document.querySelector<HTMLScriptElement>("script[src='https://sdk.mercadopago.com/js/v2']");
          if (existing) { existing.addEventListener("load", () => resolve(), { once: true }); return; }
          const s = document.createElement("script");
          s.src = "https://sdk.mercadopago.com/js/v2";
          s.onload = () => resolve();
          s.onerror = () => reject(new Error("SDK Mercado Pago indisponivel."));
          document.head.appendChild(s);
        });
      }
      const { public_key: publicKey } = await paymentsApi.publicKey();
      if (!publicKey) throw new Error("Chave publica nao configurada.");
      if (!window.MercadoPago) throw new Error("SDK nao carregado.");

      const mp = new window.MercadoPago(publicKey, { locale: "pt-BR" });

      const bin = cardNumber.replace(/\s/g, "").slice(0, 6);
      let paymentMethodId = "";
      let paymentTypeId = cardFunction === "debit" ? "debit_card" : "credit_card";
      try {
        const methods = await mp.getPaymentMethods({ bin });
        if (methods.results?.length) {
          const preferred = methods.results.find(
            (m) => m.payment_type_id === paymentTypeId
          ) ?? methods.results[0];
          paymentMethodId = preferred.id;
          paymentTypeId = preferred.payment_type_id;
        }
      } catch { /* será omitido do body se vazio */ }

      const [expMonth, expYearShort] = cardExpiry.split("/");
      const expYear = (expYearShort?.length === 2) ? `20${expYearShort}` : expYearShort;

      const token = await mp.createCardToken({
        cardNumber: cardNumber.replace(/\s/g, ""),
        cardholderName: cardName.trim(),
        cardExpirationMonth: expMonth,
        cardExpirationYear: expYear,
        securityCode: cardCvv,
        identificationType: "CPF",
        identificationNumber: cardCpf.replace(/\D/g, ""),
      });

      const cpfDigits = cardCpf.replace(/\D/g, "");
      const createdPayment = await paymentsApi.createFromBrick(createdOrder.id, {
        token: token.id,
        ...(paymentMethodId ? { payment_method_id: paymentMethodId } : {}),
        payment_type_id: paymentTypeId,
        installments: 1,
        transaction_amount: createdOrder.total,
        payer: {
          email: `cliente.${createdOrder.id.slice(0, 8)}@delivery.moschettieri.com.br`,
          ...(cpfDigits ? { identification: { type: "CPF", number: cpfDigits } } : {}),
        },
      });

      setPayment(createdPayment);
      if (createdPayment.status === "rejected" || createdPayment.status === "cancelled") {
        setPaymentState("rejected");
        setPaymentMessage("Cartao recusado pelo banco. Tente outro cartao ou pague via PIX.");
      } else {
        setPaymentState("pending");
        setPaymentMessage("Pagamento enviado. Aguardando confirmacao do banco.");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      setCardError(msg || "Erro ao processar cartao. Verifique os dados e tente novamente.");
    } finally {
      setCardSubmitting(false);
    }
  };

  const handleSwitchToPix = async () => {
    if (!createdOrder) return;
    setSelectedPaymentMethod("pix");
    setPaymentState("loading");
    setPaymentMessage("Gerando PIX seguro...");
    setCardError("");
    try {
      const pixPayment = await paymentsApi.createPix(createdOrder.id, createdOrder.total);
      setPayment(pixPayment);
      setPixExpiresAt(Date.now() + 30 * 60 * 1000);
      setPaymentState("pending");
      setPaymentMessage(
        pixPayment.qr_code_text
          ? "PIX gerado. Pague pelo QR Code ou copia-e-cola."
          : "PIX criado. Aguardando retorno do QR Code do Mercado Pago.",
      );
    } catch {
      setPaymentState("error");
      setPaymentMessage("Erro ao gerar PIX. Tente novamente.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="bg-brand-dark px-4 py-3 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate("/cart")} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <button onClick={() => navigate("/")} aria-label="Ir para a home da loja">
          <MoschettieriLogo className="text-cream text-base scale-[1.14] origin-center" />
        </button>
        <div className="w-6" />
      </div>

      <div className="px-4 pt-6 pb-36 space-y-6">
        {storeStatus && !storeStatus.is_open && storeStatus.allow_scheduled_orders && !createdOrder && (
          <section className="bg-surface-02 border border-surface-03 rounded-xl p-4">
            <h2 className="text-cream font-bold text-lg mb-2 flex items-center gap-2">
              <Clock size={20} className="text-gold" />
              Pedido agendado
            </h2>
            <p className="text-stone text-sm mb-3">A loja esta fechada, mas aceita pedidos agendados para horarios disponiveis.</p>
            <input
              type="datetime-local"
              value={scheduledFor}
              onChange={(e) => setScheduledFor(e.target.value)}
              className="w-full bg-surface-03 border border-surface-03 rounded-xl px-4 py-3 text-cream outline-none focus:border-gold"
            />
          </section>
        )}

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
                {/* Saved address selector */}
                {savedAddresses.length > 0 && !createdOrder && (
                  <div className="space-y-2">
                    <p className="text-stone text-xs font-medium ml-0.5">Escolher endereço</p>
                    <div className="space-y-2">
                      {savedAddresses.map((addr) => (
                        <button
                          key={addr.id}
                          type="button"
                          onClick={() => applyAddress(addr.id)}
                          className={`w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                            selectedAddressId === addr.id
                              ? "border-gold bg-gold/10"
                              : "border-surface-03 bg-surface-02 hover:border-brand-mid"
                          }`}
                        >
                          <MapPin size={14} className={`mt-0.5 flex-shrink-0 ${selectedAddressId === addr.id ? "text-gold" : "text-stone"}`} />
                          <div className="flex-1 min-w-0">
                            {addr.label && <p className="text-gold text-xs font-semibold leading-none mb-0.5">{addr.label}</p>}
                            <p className="text-cream text-xs">{addr.street}{addr.number ? `, ${addr.number}` : ""}</p>
                            <p className="text-stone text-[11px] truncate">
                              {[addr.neighborhood, addr.city, addr.zip_code].filter(Boolean).join(" · ")}
                            </p>
                          </div>
                          {selectedAddressId === addr.id && <Check size={14} className="text-gold flex-shrink-0 mt-0.5" />}
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={() => applyAddress("new")}
                        className={`w-full flex items-center gap-2 p-3 rounded-xl border text-left transition-all ${
                          selectedAddressId === "new"
                            ? "border-gold bg-gold/10"
                            : "border-dashed border-surface-03 hover:border-brand-mid"
                        }`}
                      >
                        <span className="text-gold text-lg leading-none">+</span>
                        <span className="text-stone text-xs">Novo endereço</span>
                      </button>
                    </div>
                  </div>
                )}
                {/* Address form — always visible for guests, visible when "new" selected for logged-in */}
                {(savedAddresses.length === 0 || selectedAddressId === "new" || !customer) && (
                  <>
                    <Field icon={Home} placeholder={c.fields.address} value={form.address} disabled={!!createdOrder} onChange={(v) => handleChange("address", v)} error={errors.address} />
                    <Field icon={MapPin} placeholder="Bairro" value={form.neighborhood} disabled={!!createdOrder} onChange={(v) => handleChange("neighborhood", v)} />
                    <Field icon={MapPin} placeholder={c.fields.city} value={form.city} disabled={!!createdOrder} onChange={(v) => handleChange("city", v)} error={errors.city} />
                    <Field icon={Hash} placeholder="CEP (opcional)" value={form.zip_code} disabled={!!createdOrder} onChange={(v) => handleChange("zip_code", v)} />
                    <Field icon={Home} placeholder={c.fields.complement} value={form.complement} disabled={!!createdOrder} onChange={(v) => handleChange("complement", v)} />
                  </>
                )}
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
            {promotionBlocksCoupons && (
              <p className="text-amber-300 text-xs mb-2">Produto em promocao neste carrinho bloqueia outros cupons.</p>
            )}
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
                  setCouponFreeShipping(false);
                  setCouponGift(null);
                }}
                disabled={promotionBlocksCoupons}
                className="flex-1 bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/70 outline-none focus:border-gold text-sm uppercase"
              />
              <button
                onClick={couponApplied ? handleRemoveCoupon : handleApplyCoupon}
                disabled={promotionBlocksCoupons || (!couponApplied && !couponCode.trim())}
                className="px-4 py-3 bg-gold hover:bg-gold/90 rounded-xl text-cream font-bold text-sm transition-colors disabled:opacity-50"
              >
                {couponApplied ? "Remover" : "Aplicar"}
              </button>
            </div>
            {couponMsg && <p className={`text-xs mt-2 ml-1 ${couponApplied ? "text-green-400" : "text-red-400"}`}>{couponMsg}</p>}
          </section>
        )}

        {!createdOrder && (
          <section>
            <h2 className="text-cream font-bold text-lg mb-3 flex items-center gap-2">
              {selectedPaymentMethod === "pix"
                ? <QrCode size={20} className="text-gold" />
                : selectedPaymentMethod === "card"
                  ? <CreditCard size={20} className="text-gold" />
                  : <Banknote size={20} className="text-gold" />}
              Forma de pagamento
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {([
                { value: "pix", label: "PIX", icon: QrCode, helper: "QR Code na tela" },
                { value: "card", label: "Cartao", icon: CreditCard, helper: "Credito ou debito" },
                { value: "delivery", label: "Na entrega", icon: Banknote, helper: "Cartao ou dinheiro" },
              ] as { value: SelectedPaymentMethod; label: string; icon: LucideIcon; helper: string }[]).map(({ value, label, icon: Icon, helper }) => {
                const disabled = value === "pix"
                  ? paymentMethods?.accept_pix === false
                  : value === "card"
                    ? paymentMethods ? !paymentMethods.accept_credit_card && !paymentMethods.accept_debit_card : false
                    : paymentMethods?.accept_cash === false;
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => !disabled && setSelectedPaymentMethod(value)}
                    disabled={disabled}
                    className={`flex items-center gap-3 rounded-xl border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${
                      selectedPaymentMethod === value
                        ? "border-gold bg-gold/10 text-gold-light"
                        : "border-surface-03 bg-surface-02 text-stone hover:border-brand-mid"
                    }`}
                  >
                    <Icon size={20} className="flex-shrink-0" />
                    <span className="min-w-0">
                      <span className="block text-sm font-bold">{label}</span>
                      <span className="block text-xs opacity-80">{disabled ? "Indisponivel" : helper}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            {selectedPaymentMethod === "delivery" && (
              <div className="mt-3 rounded-xl border border-surface-03 bg-surface-02 p-3">
                <div className="grid grid-cols-2 gap-2">
                  {([
                    { value: "card", label: "Cartao" },
                    { value: "cash", label: "Dinheiro" },
                  ] as { value: DeliveryPaymentMethod; label: string }[]).map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setDeliveryPaymentMethod(value)}
                      className={`rounded-xl border px-3 py-2 text-sm font-bold transition-colors ${
                        deliveryPaymentMethod === value
                          ? "border-gold bg-gold/10 text-gold-light"
                          : "border-surface-03 bg-surface-03 text-stone"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {deliveryPaymentMethod === "cash" && (
                  <div className="mt-3 space-y-3">
                    <label className="flex items-center gap-2 text-sm font-semibold text-parchment">
                      <input
                        type="checkbox"
                        checked={cashNeedsChange}
                        onChange={(e) => setCashNeedsChange(e.target.checked)}
                        className="h-4 w-4 accent-gold"
                      />
                      Vou precisar de troco
                    </label>
                    {cashNeedsChange && (
                      <input
                        type="text"
                        inputMode="decimal"
                        value={cashChangeFor}
                        onChange={(e) => setCashChangeFor(e.target.value.replace(/[^\d,.]/g, ""))}
                        placeholder="Troco para quanto?"
                        className="w-full bg-surface-03 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/60 outline-none focus:border-gold text-sm"
                      />
                    )}
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        <section>
          <h2 className="text-cream font-bold text-lg mb-4">{c.summaryTitle}</h2>
          <div className="space-y-3">
            {cart.map((item) => {
              const isMulti = item.flavorDivision > 1;
              const displayName = isMulti ? item.flavors.map((f) => f.name).join(" + ") : item.productData.name;
              const iconSrc = item.flavors[0]?.icon ?? item.productData.icon;
              const hasImage = isAssetUrl(iconSrc);
              return (
                <div key={item.cartItemId} className="bg-surface-02 rounded-xl p-4 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-xl overflow-hidden">
                    {hasImage
                      ? <img src={resolveAssetUrl(iconSrc)} alt={displayName} className="w-full h-full object-cover" />
                      : <span>{iconSrc || "🍕"}</span>
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-cream font-semibold text-sm truncate">{displayName}</p>
                    <p className="text-stone text-xs">{item.quantity}x - {pizzaSizeLabel(item.selectedSize)}</p>
                    {item.promotionApplied && item.promotionName && (
                      <p className="text-emerald-300 text-[11px] font-semibold mt-0.5">{item.promotionName} aplicada</p>
                    )}
                  </div>
                  <p className="text-gold font-bold text-sm flex-shrink-0">R$ {(item.finalPrice * item.quantity).toFixed(2)}</p>
                </div>
              );
            })}
            {couponGift && (
              <div className="bg-green-500/10 rounded-xl p-4 flex items-center gap-4 border border-green-500/30">
                <div className="w-12 h-12 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-xl overflow-hidden">
                  {isAssetUrl(couponGift.icon)
                    ? <img src={resolveAssetUrl(couponGift.icon)} alt={couponGift.name} className="w-full h-full object-cover" />
                    : <span>{couponGift.icon || "🎁"}</span>
                  }
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-cream font-semibold text-sm truncate">{couponGift.name}</p>
                    <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-bold text-green-300">Brinde</span>
                  </div>
                  <p className="text-stone text-xs">{couponGift.quantity}x - Cupom {couponGift.coupon_code}</p>
                </div>
                <p className="text-green-400 font-bold text-sm flex-shrink-0">R$ 0,00</p>
              </div>
            )}
            {promotionGifts.map((gift) => (
              <div key={`${gift.promotion_id}-${gift.product_id}`} className="bg-green-500/10 rounded-xl p-4 flex items-center gap-4 border border-green-500/30">
                <div className="w-12 h-12 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-xl overflow-hidden">
                  {isAssetUrl(gift.icon)
                    ? <img src={resolveAssetUrl(gift.icon)} alt={gift.name} className="w-full h-full object-cover" />
                    : <span>{gift.icon || "🎁"}</span>
                  }
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-cream font-semibold text-sm truncate">{gift.name}</p>
                    <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-bold text-green-300">Brinde</span>
                  </div>
                  <p className="text-stone text-xs">{gift.quantity}x - Promocao {gift.promotion_name}</p>
                </div>
                <p className="text-green-400 font-bold text-sm flex-shrink-0">R$ 0,00</p>
              </div>
            ))}

            <div className="bg-surface-02 rounded-xl p-4 space-y-3 border border-surface-03">
              <Line label="Subtotal:" value={`R$ ${cartSubtotal.toFixed(2)}`} />
              <Line label="Taxa de entrega:" value={deliveryFeeFinal === 0 ? "Gratis" : `R$ ${deliveryFee.toFixed(2)}`} />
              {promotionFreeShipping && <Line label="Frete gratis da promocao:" value="Aplicado" good />}
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
            <h2 className="text-cream font-bold text-lg mb-3">
              {selectedPaymentMethod === "delivery" ? "Pagamento na entrega" : "Pagamento Mercado Pago"}
            </h2>
            <p className={`text-sm mb-3 ${statusClass(paymentState)}`}>{paymentMessage || "Aguardando pagamento."}</p>
            {selectedPaymentMethod === "delivery" ? (
              <div className="rounded-xl border border-gold/25 bg-gold/10 px-4 py-3 text-sm text-parchment">
                {deliveryPaymentMethod === "cash"
                  ? cashNeedsChange
                    ? `Pagamento em dinheiro. Troco para R$ ${Number(cashChangeFor.replace(",", ".")).toFixed(2)}.`
                    : "Pagamento em dinheiro sem troco."
                  : "Pagamento com cartao na entrega."}
              </div>
            ) : selectedPaymentMethod === "pix" ? (
              <div className="space-y-4">
                {/* Timer de validade do PIX */}
                {paymentState === "pending" && pixSecondsLeft !== null && pixSecondsLeft > 0 && (
                  <div className={`flex items-center justify-between rounded-xl px-4 py-2 text-xs font-medium ${
                    pixSecondsLeft < 300 ? "bg-red-500/10 border border-red-500/30 text-red-400" : "bg-surface-03 text-stone"
                  }`}>
                    <span className="flex items-center gap-1.5"><Clock size={12} />Validade do PIX</span>
                    <span className={`font-mono font-bold ${pixSecondsLeft < 300 ? "text-red-400" : "text-cream"}`}>
                      {String(Math.floor(pixSecondsLeft / 60)).padStart(2, "0")}:{String(pixSecondsLeft % 60).padStart(2, "0")}
                    </span>
                  </div>
                )}

                {/* PIX expirado */}
                {paymentState === "expired" && (
                  <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 space-y-3">
                    <p className="text-red-400 text-sm font-semibold flex items-center gap-2">
                      <AlertCircle size={16} />PIX expirado sem pagamento.
                    </p>
                    <p className="text-stone text-xs">O pedido foi cancelado automaticamente. Você pode fazer um novo pedido quando quiser.</p>
                    <button
                      onClick={() => navigate("/")}
                      className="flex w-full items-center justify-center gap-2 rounded-xl bg-gold hover:bg-gold/90 active:scale-95 text-cream font-bold py-3 transition-colors text-sm"
                    >
                      Voltar à loja
                    </button>
                  </div>
                )}

                {paymentState !== "expired" && (
                  <>
                    {payment?.qr_code && paymentState !== "approved" && (
                      <div className="mx-auto w-full max-w-[260px] rounded-xl bg-white p-3">
                        <img src={payment.qr_code} alt="QR Code PIX" className="h-auto w-full rounded-lg" />
                      </div>
                    )}
                    {payment?.qr_code_text && paymentState !== "approved" && (
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-stone">Codigo copia-e-cola</label>
                        <textarea
                          readOnly
                          value={payment.qr_code_text}
                          rows={4}
                          className="w-full resize-none rounded-xl border border-surface-03 bg-surface-03 px-3 py-2 text-xs text-cream outline-none"
                        />
                        <button
                          type="button"
                          onClick={() => navigator.clipboard?.writeText(payment.qr_code_text || "")}
                          className="flex w-full items-center justify-center gap-2 rounded-xl bg-gold px-4 py-3 text-sm font-bold text-cream transition-colors hover:bg-gold/90"
                        >
                          <Copy size={16} />
                          Copiar codigo PIX
                        </button>
                      </div>
                    )}
                    {paymentState !== "loading" && !payment?.qr_code_text && paymentState !== "approved" && (
                      <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-200">
                        O Mercado Pago ainda nao retornou o QR Code. A tela continua verificando o pagamento.
                      </div>
                    )}
                  </>
                )}
              </div>
            ) : (
              paymentState !== "approved" && (
                <div className="space-y-3">
                  {/* Cartão recusado — oferecer PIX */}
                  {paymentState === "rejected" && (
                    <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 space-y-3">
                      <p className="text-red-400 text-sm font-semibold flex items-center gap-2">
                        <AlertCircle size={16} />
                        Cartao recusado pelo banco.
                      </p>
                      <p className="text-stone text-xs">Tente outro cartao ou pague via PIX — rapido e sem taxa.</p>
                      <button
                        onClick={handleSwitchToPix}
                        className="flex w-full items-center justify-center gap-2 rounded-xl bg-green-600 hover:bg-green-500 active:scale-95 text-white font-bold py-3 transition-colors"
                      >
                        <QrCode size={18} />
                        Pagar via PIX agora
                      </button>
                      <button
                        onClick={() => { setPaymentState("pending"); setPaymentMessage("Preencha os dados do cartao para concluir."); setCardError(""); }}
                        className="w-full text-center text-stone text-xs underline underline-offset-2"
                      >
                        Tentar com outro cartao
                      </button>
                    </div>
                  )}
                  {/* Formulário do cartão — oculto quando recusado */}
                  {paymentState !== "rejected" && (
                    <>
                      <div className="grid grid-cols-2 gap-2">
                        {(["credit", "debit"] as const).map((fn) => (
                          <button
                            key={fn}
                            type="button"
                            onClick={() => setCardFunction(fn)}
                            className={`py-2 rounded-xl border text-sm font-semibold transition-colors ${
                              cardFunction === fn
                                ? "border-gold bg-gold/10 text-gold-light"
                                : "border-surface-03 bg-surface-03 text-stone"
                            }`}
                          >
                            {fn === "credit" ? "Crédito" : "Débito"}
                          </button>
                        ))}
                      </div>
                      <div className="flex flex-col gap-2">
                        <input
                          type="text"
                          inputMode="numeric"
                          placeholder="Numero do cartao"
                          value={cardNumber}
                          onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                          maxLength={19}
                          className="w-full bg-surface-03 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/60 outline-none focus:border-gold text-sm tracking-widest"
                        />
                        <input
                          type="text"
                          placeholder="Nome no cartao (como no cartao)"
                          value={cardName}
                          onChange={(e) => setCardName(e.target.value.toUpperCase())}
                          className="w-full bg-surface-03 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/60 outline-none focus:border-gold text-sm uppercase"
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            type="text"
                            inputMode="numeric"
                            placeholder="Validade MM/AA"
                            value={cardExpiry}
                            onChange={(e) => setCardExpiry(formatExpiry(e.target.value))}
                            maxLength={5}
                            className="w-full bg-surface-03 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/60 outline-none focus:border-gold text-sm"
                          />
                          <input
                            type="text"
                            inputMode="numeric"
                            placeholder="CVV"
                            value={cardCvv}
                            onChange={(e) => setCardCvv(e.target.value.replace(/\D/g, "").slice(0, 4))}
                            maxLength={4}
                            className="w-full bg-surface-03 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/60 outline-none focus:border-gold text-sm"
                          />
                        </div>
                        <input
                          type="text"
                          inputMode="numeric"
                          placeholder="CPF do titular (opcional)"
                          value={cardCpf}
                          onChange={(e) => setCardCpf(formatCpf(e.target.value))}
                          maxLength={14}
                          className="w-full bg-surface-03 border border-surface-03 rounded-xl px-4 py-3 text-cream placeholder-stone/60 outline-none focus:border-gold text-sm"
                        />
                      </div>
                      {cardError && <p className="text-red-400 text-xs ml-1">{cardError}</p>}
                      <button
                        onClick={handleCardPay}
                        disabled={cardSubmitting || !cardNumber || !cardName || !cardExpiry || !cardCvv}
                        className="flex w-full items-center justify-center gap-2 rounded-xl bg-gold hover:bg-gold/90 active:scale-95 text-cream font-bold py-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {cardSubmitting ? <Loader2 size={20} className="animate-spin" /> : <CreditCard size={20} />}
                        {cardSubmitting ? "Processando..." : "Pagar com cartao"}
                      </button>
                      <p className="text-center text-stone text-xs">
                        Pagamento seguro via Mercado Pago. Seus dados de cartao nao sao armazenados.
                      </p>
                    </>
                  )}
                </div>
              )
            )}
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
            disabled={loading || (!shippingAvailable && deliveryMode === "delivery") || (!!storeStatus && !storeStatus.is_open && !storeStatus.allow_scheduled_orders)}
            className="w-full bg-gold hover:bg-gold/90 disabled:opacity-60 disabled:cursor-not-allowed text-cream font-bold py-4 px-4 rounded-full text-center transition-colors text-lg active:scale-95 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 size={20} className="animate-spin" />}
            {loading ? "Processando..." : storeStatus && !storeStatus.is_open && !storeStatus.allow_scheduled_orders ? "Loja fechada" : c.confirmButton}
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
