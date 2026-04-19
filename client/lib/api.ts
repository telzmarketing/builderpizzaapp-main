/**
 * API client — todas as chamadas para o backend FastAPI (porta 8000 em dev).
 *
 * A variável de ambiente VITE_API_URL permite apontar para outro host em produção.
 * Padrão de desenvolvimento: http://localhost:8000
 */

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// ─── helpers ─────────────────────────────────────────────────────────────────

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("admin_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: HeadersInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...extraHeaders,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      message = data?.error?.message ?? data?.detail ?? message;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(message);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;

  const json = await res.json();
  // FastAPI wraps responses in { success, data } envelope
  return ("data" in json ? json.data : json) as T;
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body: unknown) => request<T>("POST", path, body);
const put = <T>(path: string, body: unknown) => request<T>("PUT", path, body);
const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
const del = <T>(path: string) => request<T>("DELETE", path);

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ApiProduct {
  id: string;
  name: string;
  description: string;
  price: number;
  icon: string;
  category: string | null;
  rating: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiPromotion {
  id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  icon: string;
  validity_text: string | null;
  active: boolean;
  valid_from: string | null;
  valid_until: string | null;
}

export interface ApiMultiFlavorsConfig {
  id: number;
  max_flavors: 2 | 3;
  pricing_rule: "most_expensive" | "average" | "proportional";
  updated_at: string;
}

export interface ApiCoupon {
  id: string;
  code: string;
  description: string | null;
  icon: string;
  coupon_type: "percent" | "delivery" | "fixed";
  discount_value: number;
  min_order_value: number;
  max_uses: number | null;
  uses_count: number;
  expiry_date: string | null;
  active: boolean;
}

export interface ApiCouponApply {
  valid: boolean;
  coupon_id: string | null;
  discount_amount: number;
  message: string;
}

export interface ApiCouponUsage {
  id: string;
  coupon_id: string;
  customer_id: string | null;
  phone: string | null;
  order_id: string | null;
  created_at: string;
}

// ── Campaigns ─────────────────────────────────────────────────────────────────

export type CampaignStatus = "draft" | "active" | "paused" | "ended";
export type CampaignType = "exclusive_page" | "products_promo";
export type CpDiscountType = "percentage" | "fixed";
export type KitType = "kit" | "product" | "item";

export interface ApiCampaign {
  id: string;
  name: string;
  description: string | null;
  status: CampaignStatus;
  start_at: string | null;
  end_at: string | null;
  banner: string | null;
  slug: string;
  campaign_type: CampaignType;
  display_title: string | null;
  display_subtitle: string | null;
  display_order: number;
  published: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiCampaignProduct {
  id: string;
  campaign_id: string;
  product_id: string | null;
  kit_id: string | null;
  promotional_price: number | null;
  discount_type: CpDiscountType | null;
  discount_value: number | null;
  active: boolean;
  created_at: string;
}

export interface ApiKitItem {
  id: string;
  kit_id: string;
  product_id: string;
  quantity: number;
}

export interface ApiPromotionalKit {
  id: string;
  name: string;
  description: string | null;
  icon: string;
  kit_type: KitType;
  price_original: number;
  price_promotional: number;
  discount_type: CpDiscountType | null;
  discount_value: number | null;
  valid_until: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  items: ApiKitItem[];
}

export interface ApiOrderItem {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  selected_size: string;
  flavor_division: number;
  flavors: { product_id: string; name: string; price: number; icon: string }[];
  add_ons: string[];
  unit_price: number;
  final_price: number;
}

export type OrderStatus =
  | "pending"
  | "waiting_payment"
  | "paid"
  | "preparing"
  | "ready_for_pickup"
  | "on_the_way"
  | "delivered"
  | "cancelled"
  | "refunded";

export interface ApiOrder {
  id: string;
  customer_id: string | null;
  delivery_name: string;
  delivery_phone: string;
  delivery_street: string;
  delivery_city: string;
  delivery_complement: string | null;
  status: OrderStatus;
  subtotal: number;
  shipping_fee: number;
  discount: number;
  total: number;
  estimated_time: number;
  loyalty_points_earned: number;
  coupon_id: string | null;
  items: ApiOrderItem[];
  created_at: string;
  updated_at: string;
}

export interface CheckoutItemIn {
  product_id: string;
  quantity: number;
  selected_size: string;
  flavor_division: number;
  flavors: { product_id: string; name: string; price: number; icon: string }[];
  final_price: number;
  add_ons: string[];
}

export interface CheckoutIn {
  items: CheckoutItemIn[];
  delivery: {
    name: string;
    phone: string;
    street: string;
    city: string;
    complement?: string;
  };
  coupon_code?: string;
  customer_id?: string;
  payment_method: "pix" | "credit_card" | "cash";
}

export interface ApiPayment {
  id: string;
  order_id: string;
  method: "pix" | "credit_card" | "cash";
  status: "pending" | "approved" | "failed" | "refunded";
  amount: number;
  transaction_id: string | null;
  qr_code: string | null;
  qr_code_text: string | null;
  payment_url: string | null;
  created_at: string;
  paid_at: string | null;
}

export interface ApiLoyaltyLevel {
  id: string;
  name: string;
  min_points: number;
  max_points: number | null;
  icon: string;
  color: string;
}

export interface ApiLoyaltyReward {
  id: string;
  label: string;
  points_required: number;
  icon: string;
  active: boolean;
}

export interface ApiLoyaltyRule {
  id: string;
  label: string;
  icon: string;
  points: number;
  rule_type: string;
  active: boolean;
}

export interface ApiCustomerLoyalty {
  id: string;
  customer_id: string;
  total_points: number;
  level: ApiLoyaltyLevel | null;
}

export interface ApiCustomer {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  created_at: string;
}

export interface ApiShipping {
  shipping_price: number;
  shipping_type: string;
  rule_name: string;
  free: boolean;
  estimated_time: number;
  available: boolean;
  message: string;
}

export interface ApiDashboard {
  total_orders: number;
  total_revenue: number;
  pending_orders: number;
  total_products: number;
  total_customers: number;
  daily_revenue: { day: string; revenue: number }[];
}

export interface ApiPaymentGatewayConfig {
  id: number;
  gateway: string;
  sandbox: boolean;
  accept_pix: boolean;
  accept_credit_card: boolean;
  accept_cash: boolean;
  pix_key: string | null;
  mp_public_key: string | null;
  mp_access_token: string | null;
  stripe_publishable_key: string | null;
  stripe_secret_key: string | null;
}

export interface ApiAdmin {
  id: number;
  email: string;
  name: string;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  checkPhone: (phone: string) =>
    post<{ exists: boolean; customer_id?: string; name?: string }>(
      "/auth/check-phone",
      { phone }
    ),

  login: (phone: string, name?: string) =>
    post<{ customer: ApiCustomer; is_new: boolean }>("/auth/login", {
      phone,
      name,
    }),
};

// ─── Admin Auth ───────────────────────────────────────────────────────────────

export const adminAuthApi = {
  login: (email: string, password: string) =>
    post<{ access_token: string; token_type: string; admin: ApiAdmin }>(
      "/admin/auth/login",
      { email, password }
    ),

  me: () => get<ApiAdmin>("/admin/auth/me"),

  logout: () => post<null>("/admin/auth/logout", {}),

  changePassword: (current_password: string, new_password: string) =>
    put<{ message: string }>("/admin/auth/change-password", {
      current_password,
      new_password,
    }),
};

// ─── Products ─────────────────────────────────────────────────────────────────

export const productsApi = {
  list: (activeOnly = true) =>
    get<ApiProduct[]>(`/products${activeOnly ? "?active_only=true" : ""}`),

  get: (id: string) => get<ApiProduct>(`/products/${id}`),

  create: (data: Omit<ApiProduct, "id" | "created_at" | "updated_at">) =>
    post<ApiProduct>("/products", data),

  update: (id: string, data: Partial<Omit<ApiProduct, "id" | "created_at" | "updated_at">>) =>
    put<ApiProduct>(`/products/${id}`, data),

  remove: (id: string) => del<void>(`/products/${id}`),

  getMultiFlavorsConfig: () =>
    get<ApiMultiFlavorsConfig>("/products/config/multi-flavors"),

  updateMultiFlavorsConfig: (data: Partial<Pick<ApiMultiFlavorsConfig, "max_flavors" | "pricing_rule">>) =>
    patch<ApiMultiFlavorsConfig>("/products/config/multi-flavors", data),
};

// ─── Promotions ───────────────────────────────────────────────────────────────

export const promotionsApi = {
  list: (activeOnly = false) =>
    get<ApiPromotion[]>(`/promotions${activeOnly ? "?active_only=true" : ""}`),

  create: (data: Omit<ApiPromotion, "id">) => post<ApiPromotion>("/promotions", data),

  update: (id: string, data: Partial<Omit<ApiPromotion, "id">>) =>
    put<ApiPromotion>(`/promotions/${id}`, data),

  remove: (id: string) => del<void>(`/promotions/${id}`),
};

// ─── Orders ───────────────────────────────────────────────────────────────────

export const ordersApi = {
  checkout: (data: CheckoutIn) => post<ApiOrder>("/orders", data),

  list: (params?: { status?: OrderStatus; customer_id?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.customer_id) qs.set("customer_id", params.customer_id);
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return get<ApiOrder[]>(`/orders${q ? `?${q}` : ""}`);
  },

  get: (id: string) => get<ApiOrder>(`/orders/${id}`),

  updateStatus: (id: string, status: OrderStatus) =>
    put<ApiOrder>(`/orders/${id}/status`, { status }),

  cancel: (id: string) => post<ApiOrder>(`/orders/${id}/cancel`, {}),
};

// ─── Payments ─────────────────────────────────────────────────────────────────

export const paymentsApi = {
  create: (order_id: string, amount: number, payment_method: ApiPayment["method"]) =>
    post<ApiPayment>("/payments/create", { order_id, amount, payment_method }),

  getByOrder: (order_id: string) => get<ApiPayment>(`/payments/${order_id}`),
};

// ─── Coupons ──────────────────────────────────────────────────────────────────

export const couponsApi = {
  list: () => get<ApiCoupon[]>("/coupons"),

  create: (data: Omit<ApiCoupon, "id" | "uses_count">) =>
    post<ApiCoupon>("/coupons", data),

  update: (id: string, data: Partial<Omit<ApiCoupon, "id" | "uses_count">>) =>
    put<ApiCoupon>(`/coupons/${id}`, data),

  remove: (id: string) => del<void>(`/coupons/${id}`),

  apply: (code: string, order_subtotal: number, customer_id?: string, phone?: string) =>
    post<ApiCouponApply>("/coupons/apply", { code, order_subtotal, customer_id, phone }),

  listUsage: () => get<ApiCouponUsage[]>("/coupons/usage"),

  getCouponUsage: (id: string) => get<ApiCouponUsage[]>(`/coupons/${id}/usage`),
};

// ─── Loyalty ──────────────────────────────────────────────────────────────────

export const loyaltyApi = {
  levels: () => get<ApiLoyaltyLevel[]>("/loyalty/levels"),
  createLevel: (data: Omit<ApiLoyaltyLevel, "id">) =>
    post<ApiLoyaltyLevel>("/loyalty/levels", data),

  rewards: () => get<ApiLoyaltyReward[]>("/loyalty/rewards"),
  createReward: (data: Omit<ApiLoyaltyReward, "id">) =>
    post<ApiLoyaltyReward>("/loyalty/rewards", data),

  rules: () => get<ApiLoyaltyRule[]>("/loyalty/rules"),
  createRule: (data: Omit<ApiLoyaltyRule, "id">) =>
    post<ApiLoyaltyRule>("/loyalty/rules", data),

  account: (customer_id: string) =>
    get<ApiCustomerLoyalty>(`/loyalty/account/${customer_id}`),

  redeem: (customer_id: string, reward_id: string) =>
    post<{ message: string }>("/loyalty/redeem", { customer_id, reward_id }),
};

// ─── Shipping ─────────────────────────────────────────────────────────────────

export const shippingApi = {
  calculate: (
    city: string,
    order_subtotal: number,
    neighborhood?: string,
    zip_code?: string,
    is_pickup?: boolean,
    is_scheduled?: boolean,
  ) =>
    post<ApiShipping>("/shipping/calculate", {
      city, order_subtotal, neighborhood, zip_code, is_pickup, is_scheduled,
    }),
};

// ─── Customers ────────────────────────────────────────────────────────────────

export const customersApi = {
  list: () => get<ApiCustomer[]>("/customers"),
  get: (id: string) => get<ApiCustomer>(`/customers/${id}`),
  update: (id: string, data: { name?: string; phone?: string }) =>
    put<ApiCustomer>(`/customers/${id}`, data),
};

// ─── Campaigns ───────────────────────────────────────────────────────────────

export const campaignsApi = {
  list: (publishedOnly = false) =>
    get<ApiCampaign[]>(`/campaigns${publishedOnly ? "?published_only=true" : ""}`),

  getBySlug: (slug: string) => get<ApiCampaign>(`/campaigns/slug/${slug}`),

  get: (id: string) => get<ApiCampaign>(`/campaigns/${id}`),

  create: (data: Omit<ApiCampaign, "id" | "created_at" | "updated_at">) =>
    post<ApiCampaign>("/campaigns", data),

  update: (id: string, data: Partial<ApiCampaign>) =>
    put<ApiCampaign>(`/campaigns/${id}`, data),

  remove: (id: string) => del<void>(`/campaigns/${id}`),

  listProducts: (campaignId: string) =>
    get<ApiCampaignProduct[]>(`/campaigns/${campaignId}/products`),

  addProduct: (campaignId: string, data: Omit<ApiCampaignProduct, "id" | "campaign_id" | "created_at">) =>
    post<ApiCampaignProduct>(`/campaigns/${campaignId}/products`, data),

  removeProduct: (cpId: string) => del<void>(`/campaigns/products/${cpId}`),

  listKits: (activeOnly = false) =>
    get<ApiPromotionalKit[]>(`/campaigns/kits/all${activeOnly ? "?active_only=true" : ""}`),

  createKit: (data: Omit<ApiPromotionalKit, "id" | "created_at" | "updated_at" | "items">) =>
    post<ApiPromotionalKit>("/campaigns/kits", data),

  updateKit: (id: string, data: Partial<ApiPromotionalKit>) =>
    put<ApiPromotionalKit>(`/campaigns/kits/${id}`, data),

  removeKit: (id: string) => del<void>(`/campaigns/kits/${id}`),

  addKitItem: (kitId: string, product_id: string, quantity: number) =>
    post<ApiKitItem>(`/campaigns/kits/${kitId}/items`, { product_id, quantity }),

  removeKitItem: (itemId: string) => del<void>(`/campaigns/kits/items/${itemId}`),
};

// ─── Admin ────────────────────────────────────────────────────────────────────

export const adminApi = {
  dashboard: () => get<ApiDashboard>("/admin/dashboard"),

  getPaymentGateway: () => get<ApiPaymentGatewayConfig>("/admin/payment-gateway"),

  updatePaymentGateway: (data: Partial<ApiPaymentGatewayConfig>) =>
    put<ApiPaymentGatewayConfig>("/admin/payment-gateway", data),
};
