import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import {
  productsApi,
  promotionsApi,
  couponsApi,
  loyaltyApi,
  authApi,
  customersApi,
  type ApiProduct,
  type ApiPromotion,
  type ApiCoupon,
  type ApiLoyaltyLevel,
  type ApiLoyaltyReward,
  type ApiLoyaltyRule,
  type ApiMultiFlavorsConfig,
  type ApiCustomer,
  type ApiOrder,
  type OrderStatus,
} from "@/lib/api";

// ─── Re-export types used by pages ───────────────────────────────────────────

export type Pizza = ApiProduct;

export type FlavorDivision = 1 | 2 | 3;
export type PricingRule = "most_expensive" | "average" | "proportional";

export interface PizzaFlavor {
  productId: string;
  name: string;
  price: number;
  icon: string;
}

export interface MultiFlavorsConfig {
  maxFlavors: 2 | 3;
  pricingRule: PricingRule;
}

// ─── Cart ─────────────────────────────────────────────────────────────────────

export interface CartItem {
  cartItemId: string;
  productId: string;
  quantity: number;
  selectedSize: string;
  selectedAddOns: string[];
  productData: Pizza;
  flavorDivision: FlavorDivision;
  flavors: PizzaFlavor[];
  finalPrice: number;
  notes?: string;
}

// ─── Order (frontend view) ────────────────────────────────────────────────────

export type { ApiOrder as Order };
export type { OrderStatus };

export interface CustomerInfo {
  name: string;
  phone: string;
  address: string;
  city: string;
  complement: string;
}

// ─── Promotion ────────────────────────────────────────────────────────────────

export interface Promotion {
  id: string;
  title: string;
  subtitle: string;
  icon: string;
  active: boolean;
}

// ─── Coupon ───────────────────────────────────────────────────────────────────

export interface Coupon {
  id: string;
  code: string;
  description: string;
  discount: string;
  expiry: string;
  icon: string;
  type: "percent" | "delivery" | "fixed";
  used: boolean;
}

// ─── Fidelidade ───────────────────────────────────────────────────────────────

export interface FidelidadeLevel {
  id: string;
  name: string;
  minPoints: number;
  icon: string;
  color: string;
}

export interface FidelidadeReward {
  id: string;
  label: string;
  points: number;
  icon: string;
}

export interface EarnRule {
  id: string;
  icon: string;
  label: string;
  points: string;
}

// ─── CMS / Site Content ───────────────────────────────────────────────────────

export interface SiteContent {
  brand: { name: string; tagline: string; logo: string; pageTitle: string; faviconUrl: string };
  home: {
    sectionSubtitle: string;
    sectionTitle: string;
    categories: string[];
    bannerValidityText: string;
    bannerRotationInterval: number;
  };
  nav: { home: string; cart: string; orders: string; account: string };
  pages: {
    cart: {
      title: string;
      emptyTitle: string;
      emptySubtitle: string;
      checkoutButton: string;
      menuButton: string;
    };
    checkout: {
      title: string;
      deliveryTitle: string;
      summaryTitle: string;
      confirmButton: string;
      fields: {
        name: string;
        phone: string;
        address: string;
        city: string;
        complement: string;
      };
    };
    product: {
      pageTitle: string;
      divisionLabel: string;
      sizeLabel: string;
      addOnsLabel: string;
      quantityLabel: string;
      addToCartButton: string;
    };
    tracking: {
      pageTitle: string;
      orderNumberLabel: string;
      estimatedTimeText: string;
      statusLabels: Record<string, string>;
      statusDescriptions: Record<string, string>;
    };
    pedidos: {
      title: string;
      emptyTitle: string;
      emptySubtitle: string;
      orderButton: string;
    };
    conta: {
      title: string;
      personalDataTitle: string;
      shortcutsTitle: string;
      logoutButton: string;
      statsOrders: string;
      statsSpent: string;
    };
    fidelidade: { title: string; pointsUnit: string; redeemButton: string };
    cupons: {
      title: string;
      emptyText: string;
      copyButton: string;
      usedLabel: string;
    };
  };
  media: { logoUrl: string; heroBannerImage: string; defaultProductImage: string };
  theme: {
    primaryColor: string;
    preset: string;
  };
}

type DeepPartial<T> = { [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P] };

function deepMerge<T>(base: T, patch: DeepPartial<T>): T {
  const result = { ...base } as T;
  for (const key in patch) {
    const val = patch[key as keyof typeof patch];
    if (val !== undefined && typeof val === "object" && !Array.isArray(val)) {
      result[key as keyof T] = deepMerge(
        base[key as keyof T] as object,
        val as DeepPartial<object>
      ) as T[keyof T];
    } else if (val !== undefined) {
      result[key as keyof T] = val as T[keyof T];
    }
  }
  return result;
}

// ─── Context type ─────────────────────────────────────────────────────────────

interface AppContextType {
  // Data loading state
  loading: boolean;

  // Customer auth
  customer: ApiCustomer | null;
  customerLogin: (phone: string, name?: string) => Promise<void>;
  customerLogout: () => void;
  updateCustomer: (data: { name?: string; phone?: string }) => Promise<void>;

  // Products
  products: Pizza[];
  addProduct: (product: Omit<Pizza, "id" | "created_at" | "updated_at">) => Promise<void>;
  updateProduct: (id: string, data: Partial<Pizza>) => Promise<void>;
  deleteProduct: (id: string) => Promise<void>;

  // Cart (local only — no backend cart endpoint)
  cart: CartItem[];
  addToCart: (
    primaryProduct: Pizza,
    quantity: number,
    size: string,
    addOns: string[],
    flavors: PizzaFlavor[],
    flavorDivision: FlavorDivision,
    finalPrice: number,
    notes?: string
  ) => void;
  updateCartItem: (cartItemId: string, quantity: number, size: string, addOns: string[]) => void;
  removeFromCart: (cartItemId: string) => void;
  clearCart: () => void;
  cartSubtotal: number;
  cartDeliveryFee: number;
  cartTotal: number;

  // Promotions
  promotions: Promotion[];
  addPromotion: (promotion: Omit<Promotion, "id">) => Promise<void>;
  updatePromotion: (id: string, data: Partial<Promotion>) => Promise<void>;
  deletePromotion: (id: string) => Promise<void>;

  // Orders — agora gerenciados via API
  orders: ApiOrder[];
  setOrders: (orders: ApiOrder[]) => void;
  updateOrderStatus: (orderId: string, status: OrderStatus) => Promise<void>;

  // Coupons
  coupons: Coupon[];
  addCoupon: (coupon: Omit<Coupon, "id" | "used">) => Promise<void>;
  updateCoupon: (id: string, data: Partial<Coupon>) => Promise<void>;
  deleteCoupon: (id: string) => Promise<void>;

  // Fidelidade
  fidelidadeLevels: FidelidadeLevel[];
  setFidelidadeLevels: (levels: FidelidadeLevel[]) => void;
  fidelidadeRewards: FidelidadeReward[];
  setFidelidadeRewards: (rewards: FidelidadeReward[]) => void;
  earnRules: EarnRule[];
  setEarnRules: (rules: EarnRule[]) => void;

  // Site Content (CMS local — futuro: persistir no backend)
  siteContent: SiteContent;
  updateSiteContent: (update: DeepPartial<SiteContent>) => void;

  // Multi-Flavors Config
  multiFlavorsConfig: MultiFlavorsConfig;
  updateMultiFlavorsConfig: (update: Partial<MultiFlavorsConfig>) => Promise<void>;
}

// ─── Defaults ─────────────────────────────────────────────────────────────────

export const defaultSiteContent: SiteContent = {
  brand: { name: "Builder Pizza", tagline: "A melhor pizza da cidade", logo: "🍕", pageTitle: "Pizza Delivery App", faviconUrl: "" },
  home: {
    sectionSubtitle: "O que você quer comer hoje?",
    sectionTitle: "Escolha sua Pizza Favorita",
    categories: ["Todos", "Pizza", "Burger", "Massa"],
    bannerValidityText: "Válido até 30 Nov",
    bannerRotationInterval: 5,
  },
  nav: { home: "Home", cart: "Carrinho", orders: "Pedidos", account: "Conta" },
  pages: {
    cart: {
      title: "Meu Carrinho",
      emptyTitle: "Carrinho vazio",
      emptySubtitle: "Adicione pizzas deliciosas para começar!",
      checkoutButton: "Finalizar Pedido",
      menuButton: "Ver cardápio",
    },
    checkout: {
      title: "Checkout",
      deliveryTitle: "Endereço de Entrega",
      summaryTitle: "Resumo do Pedido",
      confirmButton: "Confirmar Pedido",
      fields: {
        name: "Nome completo",
        phone: "Telefone / WhatsApp",
        address: "Rua e número",
        city: "Cidade",
        complement: "Complemento (opcional) — apto, bloco...",
      },
    },
    product: {
      pageTitle: "Monte sua Pizza",
      divisionLabel: "Divisão da Pizza",
      sizeLabel: "Tamanho da Pizza",
      addOnsLabel: "Adicionais (opcional)",
      quantityLabel: "Quantidade",
      addToCartButton: "Adicionar ao Carrinho",
    },
    tracking: {
      pageTitle: "Acompanhar Pedido",
      orderNumberLabel: "Número do Pedido",
      estimatedTimeText: "será entregue em {time} minutos",
      statusLabels: {
        pending: "Aguardando",
        waiting_payment: "Aguardando Pagamento",
        paid: "Pagamento Confirmado",
        preparing: "Preparando",
        ready_for_pickup: "Pronto para Retirada",
        on_the_way: "A caminho",
        delivered: "Entregue",
        cancelled: "Cancelado",
        refunded: "Reembolsado",
      },
      statusDescriptions: {
        pending: "Seu pedido foi recebido e está sendo processado.",
        waiting_payment: "Aguardando confirmação do pagamento.",
        paid: "Pagamento aprovado! Seu pedido vai para a cozinha em breve.",
        preparing: "A cozinha está preparando seu pedido com carinho.",
        ready_for_pickup: "Pedido pronto! O motoboy está a caminho.",
        on_the_way: "O motoboy saiu com seu pedido.",
        delivered: "Pedido entregue. Bom apetite!",
        cancelled: "Este pedido foi cancelado.",
        refunded: "Reembolso processado.",
      },
    },
    pedidos: {
      title: "Meus Pedidos",
      emptyTitle: "Nenhum pedido ainda",
      emptySubtitle: "Seus pedidos aparecerão aqui após a primeira compra.",
      orderButton: "Fazer pedido",
    },
    conta: {
      title: "Minha Conta",
      personalDataTitle: "Dados pessoais",
      shortcutsTitle: "Atalhos",
      logoutButton: "Sair da conta",
      statsOrders: "Pedidos realizados",
      statsSpent: "Total gasto",
    },
    fidelidade: { title: "Programa de Fidelidade", pointsUnit: "pts", redeemButton: "Resgatar" },
    cupons: {
      title: "Meus Cupons",
      emptyText: "Você não possui cupons ativos no momento.",
      copyButton: "Copiar",
      usedLabel: "Utilizado",
    },
  },
  media: { logoUrl: "", heroBannerImage: "", defaultProductImage: "🍕" },
  theme: { primaryColor: "#f97316", preset: "orange" },
};

// ─── Converters (API shape → frontend shape) ──────────────────────────────────

function apiPromotionToPromotion(p: ApiPromotion): Promotion {
  return { id: p.id, title: p.title, subtitle: p.subtitle ?? "", icon: p.icon, active: p.active };
}

function apiCouponToCoupon(c: ApiCoupon): Coupon {
  let discount = "";
  if (c.coupon_type === "percent") discount = `${c.discount_value}% OFF`;
  else if (c.coupon_type === "fixed") discount = `R$${c.discount_value.toFixed(0)} OFF`;
  else discount = "Frete Grátis";

  return {
    id: c.id,
    code: c.code,
    description: c.description ?? "",
    discount,
    expiry: c.expiry_date
      ? new Date(c.expiry_date).toLocaleDateString("pt-BR")
      : "Sem validade",
    icon: c.icon,
    type: c.coupon_type,
    used: c.max_uses != null && c.uses_count >= c.max_uses,
  };
}

function apiLevelToLevel(l: ApiLoyaltyLevel): FidelidadeLevel {
  return { id: l.id, name: l.name, minPoints: l.min_points, icon: l.icon, color: l.color };
}

function apiRewardToReward(r: ApiLoyaltyReward): FidelidadeReward {
  return { id: r.id, label: r.label, points: r.points_required, icon: r.icon };
}

function apiRuleToRule(r: ApiLoyaltyRule): EarnRule {
  return { id: r.id, icon: r.icon, label: r.label, points: `+${r.points} pts` };
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [customer, setCustomer] = useState<ApiCustomer | null>(() => {
    try {
      const stored = localStorage.getItem("customer");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [products, setProducts] = useState<Pizza[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [fidelidadeLevels, setFidelidadeLevels] = useState<FidelidadeLevel[]>([]);
  const [fidelidadeRewards, setFidelidadeRewards] = useState<FidelidadeReward[]>([]);
  const [earnRules, setEarnRules] = useState<EarnRule[]>([]);
  const [siteContent, setSiteContent] = useState<SiteContent>(() => {
    try {
      const stored = localStorage.getItem("siteContent");
      if (stored) return deepMerge(defaultSiteContent, JSON.parse(stored)) as SiteContent;
    } catch { /* ignore corrupt data */ }
    return defaultSiteContent;
  });
  const [multiFlavorsConfig, setMultiFlavorsConfig] = useState<MultiFlavorsConfig>({
    maxFlavors: 3,
    pricingRule: "most_expensive",
  });

  // ── Bootstrap — fetch all data from backend on mount ──────────────────────
  useEffect(() => {
    async function bootstrap() {
      setLoading(true);
      try {
        const [prods, promos, cfgRaw, cups, levels, rewards, rules] = await Promise.allSettled([
          productsApi.list(true),
          promotionsApi.list(true),
          productsApi.getMultiFlavorsConfig(),
          couponsApi.list(),
          loyaltyApi.levels(),
          loyaltyApi.rewards(),
          loyaltyApi.rules(),
        ]);

        if (prods.status === "fulfilled") setProducts(prods.value);
        if (promos.status === "fulfilled")
          setPromotions(promos.value.map(apiPromotionToPromotion));
        if (cfgRaw.status === "fulfilled") {
          const c = cfgRaw.value;
          setMultiFlavorsConfig({ maxFlavors: c.max_flavors, pricingRule: c.pricing_rule });
        }
        if (cups.status === "fulfilled") setCoupons(cups.value.map(apiCouponToCoupon));
        if (levels.status === "fulfilled")
          setFidelidadeLevels(levels.value.map(apiLevelToLevel));
        if (rewards.status === "fulfilled")
          setFidelidadeRewards(rewards.value.map(apiRewardToReward));
        if (rules.status === "fulfilled") setEarnRules(rules.value.map(apiRuleToRule));
      } catch {
        // Se o backend não estiver disponível, continua com estado vazio
      } finally {
        setLoading(false);
      }
    }
    bootstrap();
  }, []);

  // ── Store data polling (silent refresh every 30s for store pages) ─────────
  useEffect(() => {
    async function refreshStoreData() {
      if (window.location.pathname.startsWith("/painel")) return;
      try {
        const [prods, promos] = await Promise.allSettled([
          productsApi.list(true),
          promotionsApi.list(true),
        ]);
        if (prods.status === "fulfilled") setProducts(prods.value);
        if (promos.status === "fulfilled")
          setPromotions(promos.value.map(apiPromotionToPromotion));
      } catch {
        // silent
      }
    }
    const intervalId = setInterval(refreshStoreData, 30_000);
    function handleVisibilityChange() {
      if (document.visibilityState === "visible") refreshStoreData();
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  // ── Customer auth ─────────────────────────────────────────────────────────

  const customerLogin = async (phone: string, name?: string) => {
    const { customer: c } = await authApi.login(phone, name);
    setCustomer(c);
    localStorage.setItem("customer", JSON.stringify(c));
  };

  const customerLogout = () => {
    setCustomer(null);
    localStorage.removeItem("customer");
  };

  const updateCustomer = async (data: { name?: string; phone?: string }) => {
    if (!customer) return;
    const updated = await customersApi.update(customer.id, data);
    setCustomer(updated);
    localStorage.setItem("customer", JSON.stringify(updated));
  };

  // ── Products ──────────────────────────────────────────────────────────────

  const addProduct = async (data: Omit<Pizza, "id" | "created_at" | "updated_at">) => {
    const created = await productsApi.create(data);
    setProducts((prev) => [...prev, created]);
  };

  const updateProduct = async (id: string, data: Partial<Pizza>) => {
    const updated = await productsApi.update(id, data);
    setProducts((prev) => prev.map((p) => (p.id === id ? updated : p)));
  };

  const deleteProduct = async (id: string) => {
    await productsApi.remove(id);
    setProducts((prev) => prev.filter((p) => p.id !== id));
  };

  // ── Cart ──────────────────────────────────────────────────────────────────

  const addToCart = (
    primaryProduct: Pizza,
    quantity: number,
    size: string,
    addOns: string[],
    flavors: PizzaFlavor[],
    flavorDivision: FlavorDivision,
    finalPrice: number,
    notes?: string
  ) => {
    const cartItemId = `cart-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setCart((prev) => [
      ...prev,
      { cartItemId, productId: primaryProduct.id, quantity, selectedSize: size, selectedAddOns: addOns, productData: primaryProduct, flavorDivision, flavors, finalPrice, notes },
    ]);
  };

  const updateCartItem = (cartItemId: string, quantity: number, size: string, addOns: string[]) =>
    setCart((prev) =>
      prev.map((item) =>
        item.cartItemId === cartItemId
          ? { ...item, quantity, selectedSize: size, selectedAddOns: addOns }
          : item
      )
    );

  const removeFromCart = (cartItemId: string) =>
    setCart((prev) => prev.filter((item) => item.cartItemId !== cartItemId));

  const clearCart = () => setCart([]);

  const cartSubtotal = cart.reduce((sum, item) => sum + item.finalPrice * item.quantity, 0);
  const cartDeliveryFee = cart.length > 0 ? 10.0 : 0;
  const cartTotal = cartSubtotal + cartDeliveryFee;

  // ── Promotions ────────────────────────────────────────────────────────────

  const addPromotion = async (data: Omit<Promotion, "id">) => {
    const created = await promotionsApi.create({
      title: data.title,
      subtitle: data.subtitle,
      description: null,
      icon: data.icon,
      validity_text: null,
      active: data.active,
      valid_from: null,
      valid_until: null,
    });
    setPromotions((prev) => [...prev, apiPromotionToPromotion(created)]);
  };

  const updatePromotion = async (id: string, data: Partial<Promotion>) => {
    const updated = await promotionsApi.update(id, {
      ...(data.title !== undefined && { title: data.title }),
      ...(data.subtitle !== undefined && { subtitle: data.subtitle }),
      ...(data.icon !== undefined && { icon: data.icon }),
      ...(data.active !== undefined && { active: data.active }),
    });
    setPromotions((prev) =>
      prev.map((p) => (p.id === id ? apiPromotionToPromotion(updated) : p))
    );
  };

  const deletePromotion = async (id: string) => {
    await promotionsApi.remove(id);
    setPromotions((prev) => prev.filter((p) => p.id !== id));
  };

  // ── Orders ────────────────────────────────────────────────────────────────

  const updateOrderStatus = async (orderId: string, status: OrderStatus) => {
    const { ordersApi } = await import("@/lib/api");
    const updated = await ordersApi.updateStatus(orderId, status);
    setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
  };

  // ── Coupons ───────────────────────────────────────────────────────────────

  const addCoupon = async (data: Omit<Coupon, "id" | "used">) => {
    const created = await couponsApi.create({
      code: data.code,
      description: data.description,
      icon: data.icon,
      coupon_type: data.type,
      discount_value: parseFloat(data.discount.replace(/[^0-9.]/g, "") || "0"),
      min_order_value: 0,
      max_uses: null,
      expiry_date: null,
      active: true,
    });
    setCoupons((prev) => [...prev, apiCouponToCoupon(created)]);
  };

  const updateCoupon = async (id: string, data: Partial<Coupon>) => {
    const updated = await couponsApi.update(id, {
      ...(data.code !== undefined && { code: data.code }),
      ...(data.description !== undefined && { description: data.description }),
      ...(data.icon !== undefined && { icon: data.icon }),
      ...(data.type !== undefined && { coupon_type: data.type }),
    });
    setCoupons((prev) => prev.map((c) => (c.id === id ? apiCouponToCoupon(updated) : c)));
  };

  const deleteCoupon = async (id: string) => {
    await couponsApi.remove(id);
    setCoupons((prev) => prev.filter((c) => c.id !== id));
  };

  // ── Multi-Flavors Config ──────────────────────────────────────────────────

  const updateMultiFlavorsConfig = async (update: Partial<MultiFlavorsConfig>) => {
    const updated = await productsApi.updateMultiFlavorsConfig({
      ...(update.maxFlavors !== undefined && { max_flavors: update.maxFlavors }),
      ...(update.pricingRule !== undefined && { pricing_rule: update.pricingRule }),
    });
    setMultiFlavorsConfig({ maxFlavors: updated.max_flavors, pricingRule: updated.pricing_rule });
  };

  // ── Site Content (CMS — local por enquanto) ───────────────────────────────

  const updateSiteContent = (update: DeepPartial<SiteContent>) =>
    setSiteContent((prev) => {
      const next = deepMerge(prev, update);
      try { localStorage.setItem("siteContent", JSON.stringify(next)); } catch { /* storage full */ }
      return next as SiteContent;
    });

  // ── Context value ─────────────────────────────────────────────────────────

  const value: AppContextType = {
    loading,
    customer, customerLogin, customerLogout, updateCustomer,
    products, addProduct, updateProduct, deleteProduct,
    cart, addToCart, updateCartItem, removeFromCart, clearCart,
    cartSubtotal, cartDeliveryFee, cartTotal,
    promotions, addPromotion, updatePromotion, deletePromotion,
    orders, setOrders, updateOrderStatus,
    coupons, addCoupon, updateCoupon, deleteCoupon,
    fidelidadeLevels, setFidelidadeLevels,
    fidelidadeRewards, setFidelidadeRewards,
    earnRules, setEarnRules,
    siteContent, updateSiteContent,
    multiFlavorsConfig, updateMultiFlavorsConfig,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (context === undefined) throw new Error("useApp must be used within AppProvider");
  return context;
}
