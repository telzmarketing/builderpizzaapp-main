/**
 * API client — todas as chamadas para o backend FastAPI (porta 8000 em dev).
 *
 * A variável de ambiente VITE_API_URL permite apontar para outro host em produção.
 * Padrão de desenvolvimento: http://localhost:8000
 */

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const IMAGE_FILE_RE = /\.(apng|avif|gif|jpe?g|jfif|pjpeg|pjp|png|svg|webp)$/i;

export function isAssetUrl(value?: string | null): boolean {
  const trimmed = value?.trim();
  return !!trimmed && (
    IMAGE_FILE_RE.test(trimmed) ||
    trimmed.startsWith("data:") ||
    trimmed.startsWith("http") ||
    trimmed.startsWith("/")
  );
}

export function resolveAssetUrl(value?: string | null): string {
  const trimmed = value?.trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("http") || trimmed.startsWith("data:")) return trimmed;
  if (trimmed.startsWith("/")) return `${BASE}${trimmed}`;
  if (trimmed.startsWith("uploads/")) return `${BASE}/${trimmed}`;
  if (IMAGE_FILE_RE.test(trimmed)) return `${BASE}/uploads/${trimmed}`;
  return trimmed;
}

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
    if (res.status === 401) {
      localStorage.removeItem("admin_token");
      localStorage.removeItem("admin_user");
      window.location.replace("/painel/login");
      throw new Error("Sessão expirada. Redirecionando para o login…");
    }
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

export function apiRequest<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: HeadersInit
): Promise<T> {
  return request<T>(method, path, body, extraHeaders);
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body: unknown) => request<T>("POST", path, body);
const put = <T>(path: string, body: unknown) => request<T>("PUT", path, body);
const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
const del = <T>(path: string) => request<T>("DELETE", path);

function rememberOrderAccess(order: { id: string; delivery_phone?: string | null; customer_id?: string | null }) {
  try {
    sessionStorage.setItem(
      `order_access:${order.id}`,
      JSON.stringify({
        phone: order.delivery_phone ?? null,
        customer_id: order.customer_id ?? null,
      }),
    );
  } catch {
    /* ignore storage errors */
  }
}

function orderAccessHeaders(orderId: string): HeadersInit {
  const headers: Record<string, string> = {};
  try {
    const raw = sessionStorage.getItem(`order_access:${orderId}`);
    if (raw) {
      const access = JSON.parse(raw) as { phone?: string | null; customer_id?: string | null };
      Object.assign(headers, customerAccessHeaders(access.customer_id ?? undefined));
      if (access.phone) headers["X-Customer-Phone"] = access.phone;
    } else {
      Object.assign(headers, customerAccessHeaders());
    }
  } catch {
    Object.assign(headers, customerAccessHeaders());
  }
  return headers;
}

function customerAccessHeaders(customerId?: string): HeadersInit {
  try {
    const raw = localStorage.getItem("customer");
    if (!raw) return {};
    const customer = JSON.parse(raw) as {
      id?: string;
      phone?: string | null;
      email?: string | null;
    };
    if (customerId && customer.id !== customerId) return {};

    const headers: Record<string, string> = {};
    if (customer.phone) headers["X-Customer-Phone"] = customer.phone;
    if (customer.email) headers["X-Customer-Email"] = customer.email;
    return headers;
  } catch {
    return {};
  }
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ApiProductSize {
  id: string;
  product_id: string;
  label: string;
  description: string | null;
  price: number;
  is_default: boolean;
  sort_order: number;
  active: boolean;
  created_at: string;
}

export interface ApiProductCrustType {
  id: string;
  product_id: string;
  name: string;
  price_addition: number;
  active: boolean;
  sort_order: number;
  created_at: string;
}

export interface ApiProductDrinkVariant {
  id: string;
  product_id: string;
  name: string;
  price_addition: number;
  active: boolean;
  sort_order: number;
  created_at: string;
}

export interface ApiProductCategory {
  id: string;
  parent_id: string | null;
  name: string;
  active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface ApiHomeCatalogConfig {
  id: string;
  mode: "all" | "categories" | "products";
  selected_categories: string;  // JSON string
  selected_product_ids: string; // JSON string
  show_promotions: boolean;
  updated_at: string;
}

export interface ApiProduct {
  id: string;
  name: string;
  description: string;
  price: number;
  icon: string;
  category: string | null;
  subcategory: string | null;
  product_type: string | null;  // "pizza" | "drink" | "other"
  rating: number;
  active: boolean;
  created_at: string;
  updated_at: string;
  sizes?: ApiProductSize[];
  crust_types?: ApiProductCrustType[];
  drink_variants?: ApiProductDrinkVariant[];
  standard_price?: number | null;
  current_price?: number | null;
  promotion_applied?: boolean;
  promotion_id?: string | null;
  promotion_name?: string | null;
  promotion_discount?: number;
}

export type ProductPromotionDiscountType = "fixed_price" | "amount_off" | "percent_off";

export interface ApiProductPromotionCombination {
  id?: string;
  promotion_id?: string;
  product_size_id: string | null;
  product_crust_type_id: string | null;
  active: boolean;
  promotional_value: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface ApiProductPromotion {
  id: string;
  product_id: string;
  name: string;
  active: boolean;
  valid_weekdays: number[];
  start_time: string | null;
  end_time: string | null;
  start_date: string | null;
  end_date: string | null;
  discount_type: ProductPromotionDiscountType;
  default_value: number | null;
  timezone: string;
  combinations: ApiProductPromotionCombination[];
  created_at: string;
  updated_at: string;
}

export interface ApiProductPriceQuote {
  standard_price: number;
  final_price: number;
  promotion_applied: boolean;
  promotion_id: string | null;
  promotion_name: string | null;
  discount_amount: number;
  discount_type: ProductPromotionDiscountType | null;
  promotion_blocked: boolean;
  promotion_block_reason: string | null;
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
  coupon_type: "percentage" | "fixed";
  discount_value: number;
  min_order_value: number;
  max_uses: number | null;
  max_uses_per_customer: number | null;
  used_count: number;
  expiry_date: string | null;
  active: boolean;
  campaign_id: string | null;
  created_at: string;
}

export interface ApiCouponInput {
  code?: string;
  description?: string | null;
  icon?: string;
  coupon_type?: ApiCoupon["coupon_type"];
  discount_value?: number;
  min_order_value?: number;
  max_uses?: number | null;
  max_uses_per_customer?: number | null;
  expiry_date?: string | null;
  campaign_id?: string | null;
  active?: boolean;
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

export interface TrafficCampaign {
  id: string;
  name: string;
  platform: "meta" | "google" | "tiktok" | "manual" | string;
  status: "draft" | "active" | "paused" | "ended" | string;
  daily_budget: number | null;
  total_budget: number | null;
  start_date: string | null;
  end_date: string | null;
  product_id: string | null;
  coupon_id: string | null;
  destination_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignLink {
  id: string;
  campaign_id: string;
  name: string | null;
  destination_url: string;
  final_url: string;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  utm_content: string | null;
  utm_term: string | null;
  active: boolean;
  created_at: string;
}

export interface PaidTrafficDashboard {
  spend: number;
  revenue: number;
  estimated_profit: number;
  roas: number;
  roi: number;
  cpa: number;
  average_ticket: number;
  conversion_rate: number;
  orders: number;
  paid_orders: number;
  visitors: number;
  carts: number;
  abandoned_carts: number;
  by_campaign: Array<Record<string, any>>;
  by_platform: Array<Record<string, any>>;
  by_day: Array<Record<string, any>>;
}

export interface AdIntegration {
  id: string;
  platform: string;
  status: string;
  account_name: string | null;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignSettings {
  id: string;
  attribution_window_days: number;
  attribution_model: string;
  default_margin: number;
  target_roas: number;
  tracking_enabled: boolean;
  updated_at: string;
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
  active_days: string | null;
  card_bg_color: string | null;
  media_type: string | null;
  video_url: string | null;
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
  selected_size_id?: string | null;
  flavor_division: number;
  flavor_count?: number;
  selected_crust_type_id?: string | null;
  selected_crust_type: string | null;
  selected_drink_variant: string | null;
  notes: string | null;
  flavors: { product_id: string; name: string; price: number; icon: string }[];
  add_ons: string[];
  unit_price: number;
  final_price: number;
  standard_unit_price?: number | null;
  applied_unit_price?: number | null;
  promotion_id?: string | null;
  promotion_name?: string | null;
  promotion_discount?: number;
  promotion_applied?: boolean;
  promotion_blocked?: boolean;
  promotion_block_reason?: string | null;
}

export type OrderStatus =
  | "pending"
  | "waiting_payment"
  | "paid"
  | "aguardando_pagamento"
  | "pago"
  | "pagamento_recusado"
  | "pagamento_expirado"
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
  is_scheduled?: boolean;
  scheduled_for?: string | null;
  coupon_id: string | null;
  pedido_status?: OrderStatus;
  payment_status?: ApiPayment["status"] | "pending";
  external_reference?: string | null;
  items: ApiOrderItem[];
  created_at: string;
  updated_at: string;
  paid_at: string | null;
  preparation_started_at: string | null;
  out_for_delivery_at: string | null;
  delivered_at: string | null;
  target_delivery_minutes: number;
  total_time_minutes: number | null;
  preparation_time_minutes: number | null;
  delivery_time_minutes: number | null;
}

export interface CheckoutItemIn {
  product_id: string;
  quantity: number;
  selected_size: string;
  selected_size_id?: string | null;
  flavor_division: number;
  flavors: { product_id: string; name: string; price: number; icon: string }[];
  final_price: number;
  add_ons: string[];
  selected_crust_type_id?: string | null;
  selected_crust_type_name?: string | null;
  selected_drink_variant_id?: string | null;
  selected_drink_variant_name?: string | null;
  notes?: string | null;
}

export interface CheckoutIn {
  items: CheckoutItemIn[];
  delivery: {
    name: string;
    phone: string;
    street: string;
    city: string;
    neighborhood?: string;
    zip_code?: string;
    complement?: string;
    is_pickup?: boolean;
    is_scheduled?: boolean;
    scheduled_for?: string | null;
  };
  coupon_code?: string;
  customer_id?: string;
  payment_method: "pix" | "credit_card" | "cash";
  campaign_id?: string | null;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_content?: string | null;
  utm_term?: string | null;
  session_id?: string | null;
  landing_page?: string | null;
  referrer?: string | null;
}

export interface StoreOperationInterval {
  id?: string;
  schedule_id?: string;
  tenant_id?: string;
  open_time: string;
  close_time: string;
  created_at?: string;
}

export interface StoreWeeklySchedule {
  id?: string;
  tenant_id?: string;
  weekday: number;
  active: boolean;
  intervals: StoreOperationInterval[];
  created_at?: string;
  updated_at?: string;
}

export interface StoreOperationSettings {
  id?: string;
  tenant_id?: string;
  manual_mode: "auto" | "manual_closed" | "manual_open";
  closed_message: string;
  allow_scheduled_orders: boolean;
  timezone: string;
  created_at?: string;
  updated_at?: string;
}

export interface StoreOperationException {
  id: string;
  tenant_id?: string;
  date: string;
  exception_type: "closed" | "special_hours";
  open_time: string | null;
  close_time: string | null;
  reason: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface StoreOperationConfig {
  settings: StoreOperationSettings;
  weekly_schedules: StoreWeeklySchedule[];
  exceptions: StoreOperationException[];
}

export interface StoreOperationStatus {
  is_open: boolean;
  mode: string;
  status_label: string;
  message: string;
  current_weekday: number;
  today_hours: string;
  next_opening_at: string | null;
  next_opening_label: string | null;
  allow_scheduled_orders: boolean;
}

export interface StoreOperationLog {
  id: string;
  tenant_id: string;
  admin_id: string | null;
  admin_email: string | null;
  action: string;
  entity: string;
  entity_id: string | null;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
}

export interface ApiPayment {
  id: string;
  order_id: string;
  method: "pix" | "credit_card" | "debit_card" | "cash";
  status: "pending" | "approved" | "rejected" | "cancelled" | "expired" | "paid" | "failed" | "refunded";
  amount: number;
  provider: string | null;
  mercado_pago_payment_id: string | null;
  external_reference: string | null;
  transaction_id: string | null;
  qr_code: string | null;
  qr_code_text: string | null;
  payment_url: string | null;
  created_at: string;
  paid_at: string | null;
}

export interface ApiPaymentStatus {
  order_id: string;
  pedido_status: OrderStatus;
  payment_status: ApiPayment["status"] | "pending";
  mercado_pago_payment_id: string | null;
  external_reference: string | null;
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

export interface ApiLoyaltySettings {
  id: string;
  enabled: boolean;
  points_per_real: number;
  updated_at: string;
}

export interface ApiLoyaltyBenefit {
  id: string;
  level_id: string;
  benefit_type: "product" | "discount" | "frete_gratis" | "experience";
  label: string;
  description: string | null;
  value: number;
  min_order_value: number;
  expires_in_days: number | null;
  usage_limit: number;
  stackable: boolean;
  active: boolean;
  created_at: string;
}

export interface ApiLoyaltyCycle {
  id: string;
  customer_id: string;
  start_date: string;
  end_date: string;
  points_earned: number;
  points_used: number;
  points_expired: number;
  points_rolled_over: number;
  level_reached: string | null;
  status: "active" | "closed";
  created_at: string;
  closed_at: string | null;
}

export interface ApiReferral {
  id: string;
  referrer_id: string;
  referred_id: string | null;
  referral_code: string;
  status: "pending" | "completed" | "cancelled";
  reward_points: number;
  created_at: string;
  completed_at: string | null;
}

export interface ApiCustomerLoyalty {
  id: string;
  customer_id: string;
  total_points: number;
  rollover_points: number;
  lifetime_points: number;
  cycle_start_date: string | null;
  cycle_end_date: string | null;
  benefit_expiration_date: string | null;
  last_activity_at: string | null;
  level: ApiLoyaltyLevel | null;
  transactions: ApiLoyaltyTransaction[];
  benefits: ApiLoyaltyBenefit[];
  cycles: ApiLoyaltyCycle[];
}

export interface ApiLoyaltyTransaction {
  id: string;
  order_id: string | null;
  points: number;
  transaction_type: string;
  description: string | null;
  created_at: string;
}

export interface ApiAddress {
  id: string;
  customer_id: string;
  label?: string | null;
  street: string;
  number?: string | null;
  complement?: string | null;
  neighborhood?: string | null;
  city: string;
  state?: string | null;
  zip_code?: string | null;
  is_default: boolean;
  created_at: string;
}

export interface ApiCustomer {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  lgpd_consent: boolean;
  lgpd_policy_version: string | null;
  marketing_email_consent: boolean;
  marketing_whatsapp_consent: boolean;
  crm_status?: string | null;
  source?: string | null;
  notes?: string | null;
  tags?: string | null;
  last_contact_at?: string | null;
  utm_source?: string | null;
  utm_campaign?: string | null;
  created_at: string;
  addresses: ApiAddress[];
}

export interface ApiLgpdPolicy {
  id: string;
  version: string;
  title: string;
  intro_text: string | null;
  data_controller_text: string | null;
  data_collected_text: string | null;
  data_usage_text: string | null;
  data_retention_text: string | null;
  rights_text: string | null;
  contact_text: string | null;
  marketing_email_label: string | null;
  marketing_whatsapp_label: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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

// ── Exit Popup ────────────────────────────────────────────────────────────────

export interface ApiExitPopupConfig {
  enabled: boolean;
  title: string;
  subtitle: string;
  coupon_code: string | null;
  button_text: string;
  image_url: string | null;
  show_once_per_session: boolean;
  updated_at: string | null;
}

export const exitPopupApi = {
  get: () => get<ApiExitPopupConfig>("/exit-popup"),
  update: (body: Partial<ApiExitPopupConfig>) => put<ApiExitPopupConfig>("/exit-popup", body),
};

// ── Admin Users + RBAC ────────────────────────────────────────────────────────

export interface ApiAdminUser {
  id: string;
  name: string;
  email: string;
  active: boolean;
  phone?: string | null;
  role_id?: string | null;
  role_name?: string | null;
  store_id?: string | null;
  last_login_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiRole {
  id: string;
  name: string;
  description?: string | null;
  is_system: boolean;
  user_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ApiModule {
  id: string;
  key: string;
  name: string;
  description?: string | null;
  parent_id?: string | null;
  order_index: number;
  is_active: boolean;
}

export interface ApiPermission {
  id: string;
  key: string;
  name: string;
  description?: string | null;
}

export interface ApiRolePermission {
  module_id: string;
  permission_id: string;
  allowed: boolean;
}

export interface ApiAuditLog {
  id: string;
  user_id?: string | null;
  user_name?: string | null;
  action: string;
  module_key?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  old_value?: string | null;
  new_value?: string | null;
  ip_address?: string | null;
  created_at: string;
}

export interface ApiEffectivePermissions {
  is_master: boolean;
  role_id?: string | null;
  role_name?: string | null;
  modules: Record<string, Record<string, boolean>>;
}

export const adminUsersApi = {
  list: () => get<ApiAdminUser[]>("/admin/users"),
  create: (body: {
    name: string; email: string; password: string; active?: boolean;
    phone?: string; role_id?: string; store_id?: string;
  }) => post<ApiAdminUser>("/admin/users", body),
  update: (id: string, body: {
    name?: string; email?: string; active?: boolean; password?: string;
    phone?: string; role_id?: string | null; store_id?: string | null;
  }) => put<ApiAdminUser>(`/admin/users/${id}`, body),
  toggleStatus: (id: string) => patch<ApiAdminUser>(`/admin/users/${id}/status`, {}),
  resetPassword: (id: string, new_password: string) =>
    patch<null>(`/admin/users/${id}/reset-password`, { new_password }),
  remove: (id: string) => del<null>(`/admin/users/${id}`),
};

export const rbacApi = {
  // Roles
  listRoles: () => get<ApiRole[]>("/admin/roles"),
  createRole: (body: { name: string; description?: string }) =>
    post<ApiRole>("/admin/roles", body),
  updateRole: (id: string, body: { name?: string; description?: string }) =>
    put<ApiRole>(`/admin/roles/${id}`, body),
  deleteRole: (id: string) => del<null>(`/admin/roles/${id}`),
  duplicateRole: (id: string) => post<ApiRole>(`/admin/roles/${id}/duplicate`, {}),

  // Modules & permissions
  listModules: () => get<ApiModule[]>("/admin/modules"),
  listPermissions: () => get<ApiPermission[]>("/admin/permissions"),

  // Role permission matrix
  getRolePermissions: (roleId: string) => get<ApiRolePermission[]>(`/admin/roles/${roleId}/permissions`),
  updateRolePermissions: (roleId: string, permissions: ApiRolePermission[]) =>
    put<null>(`/admin/roles/${roleId}/permissions`, { permissions }),

  // User permission overrides
  getUserPermissions: (userId: string) => get<ApiRolePermission[]>(`/admin/users/${userId}/permissions`),
  updateUserPermissions: (userId: string, permissions: ApiRolePermission[]) =>
    put<null>(`/admin/users/${userId}/permissions`, { permissions }),

  // Audit logs
  getAuditLogs: (params?: { user_id?: string; module_key?: string; action?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.user_id) qs.set("user_id", params.user_id);
    if (params?.module_key) qs.set("module_key", params.module_key);
    if (params?.action) qs.set("action", params.action);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return get<{ total: number; items: ApiAuditLog[] }>(`/admin/audit-logs${q ? `?${q}` : ""}`);
  },

  // Effective permissions for current session
  myPermissions: () => get<ApiEffectivePermissions>("/admin/auth/me/permissions"),
};

export interface ApiDashboard {
  total_orders: number;
  waiting_payment_orders: number;
  total_revenue: number;
  pending_orders: number;
  total_products: number;
  total_customers: number;
  daily_revenue: { day: string; revenue: number }[];
}

export interface ApiPaymentGatewayConfig {
  id: string;
  gateway: string;
  sandbox: boolean;
  accept_pix: boolean;
  accept_credit_card: boolean;
  accept_debit_card: boolean;
  accept_cash: boolean;
  pix_key: string | null;
  pix_key_type: string | null;
  pix_beneficiary_name: string | null;
  pix_beneficiary_city: string | null;
  mp_public_key: string | null;
  mp_access_token_masked: string | null;
  stripe_publishable_key: string | null;
  stripe_secret_key_masked: string | null;
  pagseguro_email: string | null;
  pagseguro_token_masked: string | null;
  updated_at: string;
}

export interface ApiPaymentGatewayConfigUpdate {
  gateway?: string;
  sandbox?: boolean;
  accept_pix?: boolean;
  accept_credit_card?: boolean;
  accept_debit_card?: boolean;
  accept_cash?: boolean;
  pix_key?: string | null;
  pix_key_type?: string | null;
  pix_beneficiary_name?: string | null;
  pix_beneficiary_city?: string | null;
  mp_public_key?: string | null;
  mp_access_token?: string | null;
  mp_webhook_secret?: string | null;
  stripe_publishable_key?: string | null;
  stripe_secret_key?: string | null;
  stripe_webhook_secret?: string | null;
  pagseguro_email?: string | null;
  pagseguro_token?: string | null;
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

  googleLogin: (credential: string) =>
    post<{ customer: ApiCustomer; is_new: boolean }>("/auth/google", { credential }),

  emailLogin: (email: string) =>
    post<{ customer: ApiCustomer; is_new: boolean }>("/auth/login-email", { email }),

  register: (data: {
    name: string; email: string; phone: string;
    street: string; number: string; complement?: string;
    neighborhood: string; city: string; state?: string; zip_code: string;
    label?: string;
    lgpd_consent: boolean; lgpd_policy_version?: string;
    marketing_email_consent?: boolean; marketing_whatsapp_consent?: boolean;
  }) => post<{ customer: ApiCustomer; is_new: boolean }>("/auth/register", data),
};

// ─── LGPD ─────────────────────────────────────────────────────────────────────

export const lgpdApi = {
  current: () => get<ApiLgpdPolicy | null>("/lgpd/current"),
  list: () => get<ApiLgpdPolicy[]>("/admin/lgpd"),
  create: (data: Omit<ApiLgpdPolicy, "id" | "created_at" | "updated_at">) =>
    post<ApiLgpdPolicy>("/admin/lgpd", data),
  update: (id: string, data: Partial<Omit<ApiLgpdPolicy, "id" | "created_at" | "updated_at">>) =>
    put<ApiLgpdPolicy>(`/admin/lgpd/${id}`, data),
  remove: (id: string) => del<void>(`/admin/lgpd/${id}`),
  activate: (id: string) => post<ApiLgpdPolicy>(`/admin/lgpd/${id}/activate`, {}),
  seedDefault: () => post<{ message?: string; id?: string }>("/admin/lgpd/seed-default", {}),
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

export const categoriesApi = {
  list: (activeOnly = false) =>
    get<ApiProductCategory[]>(`/products/categories${activeOnly ? "?active_only=true" : ""}`),

  create: (data: Omit<ApiProductCategory, "id" | "created_at" | "updated_at">) =>
    post<ApiProductCategory>("/products/categories", data),

  update: (id: string, data: Partial<Omit<ApiProductCategory, "id" | "created_at" | "updated_at">>) =>
    put<ApiProductCategory>(`/products/categories/${id}`, data),

  remove: (id: string) => del<void>(`/products/categories/${id}`),
};

// ─── Product Sizes ────────────────────────────────────────────────────────────

export const sizesApi = {
  list: (productId: string, activeOnly = true) =>
    get<ApiProductSize[]>(`/products/${productId}/sizes${activeOnly ? "" : "?active_only=false"}`),

  create: (productId: string, data: Omit<ApiProductSize, "id" | "product_id" | "created_at">) =>
    post<ApiProductSize>(`/products/${productId}/sizes`, data),

  update: (productId: string, sizeId: string, data: Partial<Omit<ApiProductSize, "id" | "product_id" | "created_at">>) =>
    put<ApiProductSize>(`/products/${productId}/sizes/${sizeId}`, data),

  remove: (productId: string, sizeId: string) =>
    del<void>(`/products/${productId}/sizes/${sizeId}`),
};

// ─── Crust Types ──────────────────────────────────────────────────────────────

export const crustApi = {
  list: (productId: string, activeOnly = true) =>
    get<ApiProductCrustType[]>(`/products/${productId}/crusts${activeOnly ? "" : "?active_only=false"}`),

  create: (productId: string, data: Omit<ApiProductCrustType, "id" | "product_id" | "created_at">) =>
    post<ApiProductCrustType>(`/products/${productId}/crusts`, data),

  update: (productId: string, crustId: string, data: Partial<Omit<ApiProductCrustType, "id" | "product_id" | "created_at">>) =>
    put<ApiProductCrustType>(`/products/${productId}/crusts/${crustId}`, data),

  remove: (productId: string, crustId: string) =>
    del<void>(`/products/${productId}/crusts/${crustId}`),
};

// ─── Drink Variants ───────────────────────────────────────────────────────────

export const productPromotionsApi = {
  list: (productId: string) =>
    get<ApiProductPromotion[]>(`/products/${productId}/promotions`),

  create: (productId: string, data: Omit<ApiProductPromotion, "id" | "product_id" | "created_at" | "updated_at">) =>
    post<ApiProductPromotion>(`/products/${productId}/promotions`, data),

  update: (productId: string, promotionId: string, data: Partial<Omit<ApiProductPromotion, "id" | "product_id" | "created_at" | "updated_at">>) =>
    put<ApiProductPromotion>(`/products/${productId}/promotions/${promotionId}`, data),

  remove: (productId: string, promotionId: string) =>
    del<void>(`/products/${productId}/promotions/${promotionId}`),

  quote: (productId: string, params?: { size_id?: string | null; crust_id?: string | null; flavor_count?: number; flavor_ids?: string[] }) => {
    const search = new URLSearchParams();
    if (params?.size_id) search.set("size_id", params.size_id);
    if (params?.crust_id) search.set("crust_id", params.crust_id);
    if (params?.flavor_count) search.set("flavor_count", String(params.flavor_count));
    params?.flavor_ids?.forEach((id) => search.append("flavor_ids", id));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return get<ApiProductPriceQuote>(`/products/${productId}/price${suffix}`);
  },
};

export const drinkVariantApi = {
  list: (productId: string, activeOnly = true) =>
    get<ApiProductDrinkVariant[]>(`/products/${productId}/drink-variants${activeOnly ? "" : "?active_only=false"}`),

  create: (productId: string, data: Omit<ApiProductDrinkVariant, "id" | "product_id" | "created_at">) =>
    post<ApiProductDrinkVariant>(`/products/${productId}/drink-variants`, data),

  update: (productId: string, variantId: string, data: Partial<Omit<ApiProductDrinkVariant, "id" | "product_id" | "created_at">>) =>
    put<ApiProductDrinkVariant>(`/products/${productId}/drink-variants/${variantId}`, data),

  remove: (productId: string, variantId: string) =>
    del<void>(`/products/${productId}/drink-variants/${variantId}`),
};

// ─── Home Catalog Config ──────────────────────────────────────────────────────

export const homeCatalogApi = {
  get: () => get<ApiHomeCatalogConfig>("/home-config"),

  update: (data: {
    mode?: string;
    selected_categories?: string[];
    selected_product_ids?: string[];
    show_promotions?: boolean;
  }) => put<ApiHomeCatalogConfig>("/home-config", data),
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
  checkout: async (data: CheckoutIn) => {
    const order = await post<ApiOrder>("/orders", data);
    rememberOrderAccess(order);
    return order;
  },

  list: (params?: { status?: OrderStatus; customer_id?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.customer_id) qs.set("customer_id", params.customer_id);
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return request<ApiOrder[]>(
      "GET",
      `/orders${q ? `?${q}` : ""}`,
      undefined,
      params?.customer_id ? customerAccessHeaders(params.customer_id) : undefined,
    );
  },

  get: (id: string) =>
    request<ApiOrder>("GET", `/orders/${id}`, undefined, orderAccessHeaders(id)),

  paymentStatus: (id: string) =>
    request<ApiPaymentStatus>("GET", `/orders/${id}/payment-status`, undefined, orderAccessHeaders(id)),

  updateStatus: (id: string, status: OrderStatus) =>
    put<ApiOrder>(`/orders/${id}/status`, { status }),

  cancel: (id: string) => post<ApiOrder>(`/orders/${id}/cancel`, {}),
};

// ─── Payments ─────────────────────────────────────────────────────────────────

export const storeOperationApi = {
  status: () => get<StoreOperationStatus>("/store-operation/status"),
  config: () => get<StoreOperationConfig>("/store-operation/config"),
  updateSettings: (data: StoreOperationSettings) =>
    put<StoreOperationSettings>("/store-operation/settings", data),
  updateWeeklySchedules: (data: StoreWeeklySchedule[]) =>
    put<StoreWeeklySchedule[]>("/store-operation/weekly-schedules", data),
  createException: (data: Omit<StoreOperationException, "id" | "tenant_id" | "created_at" | "updated_at">) =>
    post<StoreOperationException>("/store-operation/exceptions", data),
  updateException: (id: string, data: Omit<StoreOperationException, "id" | "tenant_id" | "created_at" | "updated_at">) =>
    put<StoreOperationException>(`/store-operation/exceptions/${id}`, data),
  removeException: (id: string) => del<void>(`/store-operation/exceptions/${id}`),
  logs: (limit = 100) => get<StoreOperationLog[]>(`/store-operation/logs?limit=${limit}`),
};

export const paymentsApi = {
  create: (order_id: string, amount: number, payment_method: ApiPayment["method"]) =>
    request<ApiPayment>(
      "POST",
      "/payments/create",
      { order_id, amount, payment_method },
      orderAccessHeaders(order_id),
    ),

  createFromBrick: (order_id: string, formData: Record<string, unknown>) =>
    request<ApiPayment>(
      "POST",
      "/payments/create",
      { order_id, formData },
      orderAccessHeaders(order_id),
    ),

  getByOrder: (order_id: string) =>
    request<ApiPayment>("GET", `/payments/${order_id}`, undefined, orderAccessHeaders(order_id)),

  publicKey: () => get<{ public_key: string }>("/payments/public-key"),
};

// ─── Coupons ──────────────────────────────────────────────────────────────────

export const couponsApi = {
  list: () => get<ApiCoupon[]>("/coupons"),

  publicList: () => get<ApiCoupon[]>("/coupons/public"),

  create: (data: ApiCouponInput & { code: string; discount_value: number }) =>
    post<ApiCoupon>("/coupons", data),

  update: (id: string, data: ApiCouponInput) =>
    put<ApiCoupon>(`/coupons/${id}`, data),

  remove: (id: string) => del<void>(`/coupons/${id}`),

  apply: (code: string, order_subtotal: number, customer_id?: string, phone?: string) =>
    post<ApiCouponApply>("/coupons/apply", { code, order_subtotal, customer_id, phone }),

  listUsage: () => get<ApiCouponUsage[]>("/coupons/usage"),

  getCouponUsage: (id: string) => get<ApiCouponUsage[]>(`/coupons/${id}/usage`),
};

// ─── Loyalty ──────────────────────────────────────────────────────────────────

export const loyaltyApi = {
  settings: () => get<ApiLoyaltySettings>("/loyalty/settings"),
  updateSettings: (data: Pick<ApiLoyaltySettings, "enabled" | "points_per_real">) =>
    put<ApiLoyaltySettings>("/loyalty/settings", data),

  levels: () => get<ApiLoyaltyLevel[]>("/loyalty/levels"),
  createLevel: (data: Omit<ApiLoyaltyLevel, "id">) =>
    post<ApiLoyaltyLevel>("/loyalty/levels", data),
  updateLevel: (id: string, data: Omit<ApiLoyaltyLevel, "id">) =>
    put<ApiLoyaltyLevel>(`/loyalty/levels/${id}`, data),
  deleteLevel: (id: string) => del<void>(`/loyalty/levels/${id}`),

  rewards: () => get<ApiLoyaltyReward[]>("/loyalty/rewards"),
  createReward: (data: Omit<ApiLoyaltyReward, "id">) =>
    post<ApiLoyaltyReward>("/loyalty/rewards", data),
  deleteReward: (id: string) => del<void>(`/loyalty/rewards/${id}`),

  rules: () => get<ApiLoyaltyRule[]>("/loyalty/rules"),
  createRule: (data: Omit<ApiLoyaltyRule, "id">) =>
    post<ApiLoyaltyRule>("/loyalty/rules", data),
  deleteRule: (id: string) => del<void>(`/loyalty/rules/${id}`),

  benefits: (levelId?: string) =>
    get<ApiLoyaltyBenefit[]>(`/loyalty/benefits${levelId ? `?level_id=${levelId}` : ""}`),
  createBenefit: (data: Omit<ApiLoyaltyBenefit, "id" | "created_at">) =>
    post<ApiLoyaltyBenefit>("/loyalty/benefits", data),
  updateBenefit: (id: string, data: Omit<ApiLoyaltyBenefit, "id" | "created_at">) =>
    put<ApiLoyaltyBenefit>(`/loyalty/benefits/${id}`, data),
  deleteBenefit: (id: string) => del<void>(`/loyalty/benefits/${id}`),
  redeemBenefit: (customer_id: string, benefit_id: string, order_id?: string) =>
    request<{ message: string }>(
      "POST",
      "/loyalty/benefits/redeem",
      { customer_id, benefit_id, order_id },
      customerAccessHeaders(customer_id),
    ),

  account: (customer_id: string) =>
    request<ApiCustomerLoyalty>(
      "GET",
      `/loyalty/account/${customer_id}`,
      undefined,
      customerAccessHeaders(customer_id),
    ),

  redeem: (customer_id: string, reward_id: string) =>
    request<{ message: string }>(
      "POST",
      "/loyalty/redeem",
      { customer_id, reward_id },
      customerAccessHeaders(customer_id),
    ),

  // Admin
  adminCustomers: (level_id?: string) =>
    get<ApiCustomerLoyalty[]>(`/loyalty/admin/customers${level_id ? `?level_id=${level_id}` : ""}`),
  adminAdjustPoints: (customer_id: string, points: number, description: string) =>
    post<{ total_points: number }>("/loyalty/admin/points", { customer_id, points, description }),
  adminCloseCycle: (customer_id: string) =>
    post<{ message: string }>("/loyalty/admin/close-cycle", { customer_id }),
  adminCycles: (customer_id: string) =>
    get<ApiLoyaltyCycle[]>(`/loyalty/admin/cycles/${customer_id}`),

  // Referrals
  getReferral: (customer_id: string) =>
    request<ApiReferral>(
      "GET",
      `/loyalty/referral/${customer_id}`,
      undefined,
      customerAccessHeaders(customer_id),
    ),
  completeReferral: (referral_code: string, customer_id: string) =>
    request<{ message: string }>(
      "POST",
      "/loyalty/referral/complete",
      { referral_code, customer_id },
      customerAccessHeaders(customer_id),
    ),
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

// ─── Customer extended types ──────────────────────────────────────────────────

export interface ApiCustomerOrderItem {
  id: string;
  product_id: string;
  quantity: number;
  selected_size: string | null;
  selected_crust_type: string | null;
  selected_drink_variant: string | null;
  notes: string | null;
  flavors: Array<{ name: string; price: number }>;
  unit_price: number;
}

export interface ApiCustomerOrder {
  id: string;
  status: string;
  total: number;
  subtotal: number;
  shipping_fee: number;
  discount: number;
  created_at: string;
  paid_at: string | null;
  delivered_at: string | null;
  delivery_name: string;
  delivery_street: string;
  delivery_city: string;
  delivery_complement: string | null;
  coupon_id: string | null;
  total_time_minutes: number | null;
  estimated_time: number | null;
  items: ApiCustomerOrderItem[];
  payment_status: string;
}

export interface ApiCustomerEvent {
  id: string;
  session_id: string | null;
  event_type: string;
  event_name: string | null;
  event_description: string | null;
  product_id: string | null;
  order_id: string | null;
  campaign_id: string | null;
  coupon_id: string | null;
  metadata_json: string | null;
  source: string | null;
  utm_source: string | null;
  utm_campaign: string | null;
  device_type: string | null;
  browser: string | null;
  page_url: string | null;
  created_at: string;
}

export interface ApiCustomerSummary {
  customer: {
    id: string;
    name: string;
    email: string | null;
    phone: string | null;
    crm_status: string | null;
    source: string | null;
    utm_source: string | null;
    utm_campaign: string | null;
    created_at: string;
  };
  orders: {
    total: number;
    total_spent: number;
    avg_ticket: number;
    paid: number;
    delivered: number;
    cancelled: number;
    last_order_at: string | null;
    first_order_at: string | null;
  };
  behavior: {
    status: string;
    total_visits: number;
    products_viewed: number;
    cart_abandonments: number;
    checkout_abandonments: number;
    last_activity_at: string | null;
  };
}

export interface ApiCustomerTag {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  color: string;
  status: string;
  source: string;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  member_count?: number;
  assignment_id?: string;
  assignment_source?: string;
  assigned_at?: string | null;
}

export interface ApiCustomerSegmentRule {
  field: string;
  operator: string;
  value: string;
}

export interface ApiCustomerSegment {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  description: string | null;
  rules: ApiCustomerSegmentRule[];
  status: string;
  source: string;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApiCustomerGroup {
  id: string;
  name: string;
  description: string | null;
  group_type: string;
  color: string | null;
  icon: string | null;
  member_count: number | null;
  created_at: string | null;
  rules?: Array<{ field: string; operator: string; value: string }>;
  member_id?: string;
  member_source?: string | null;
  added_at?: string | null;
}

export interface ApiSegmentPreview {
  total: number;
  customers: Array<{
    id: string;
    name: string;
    email: string | null;
    phone: string | null;
    crm_status: string | null;
    total_orders: number;
    total_spent: number;
    avg_ticket: number;
    last_order_at: string | null;
  }>;
  message?: string;
}

export interface ApiCustomerAIProfile {
  id: string;
  customer_id: string;
  profile_summary: string;
  segment: string;
  preferences: {
    favorite_products?: Array<{ name: string; count: number }>;
    favorite_categories?: Array<{ name: string; count: number }>;
    favorite_flavors?: Array<{ name: string; count: number }>;
    favorite_sizes?: Array<{ name: string; count: number }>;
    favorite_crusts?: Array<{ name: string; count: number }>;
    favorite_drinks?: Array<{ name: string; count: number }>;
    best_purchase_days?: Array<{ name: string; count: number }>;
    best_purchase_hours?: Array<{ name: string; count: number }>;
  };
  behavior: {
    total_orders?: number;
    total_spent?: number;
    average_ticket?: number;
    last_order_at?: string | null;
    days_since_last_order?: number | null;
    cart_abandonments?: number;
    checkout_abandonments?: number;
    visits_without_purchase?: number;
    coupon_events?: number;
    campaign_events?: number;
    chatbot_interactions?: number;
  };
  churn_risk: string;
  repurchase_probability: number;
  average_ticket: number;
  best_contact_day: string | null;
  best_contact_hour: string | null;
  next_best_action: string | null;
  recommended_offer: string | null;
  recommended_message: string | null;
  analysis_source: string;
  model_version: string;
  generated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApiCustomerAISuggestion {
  id: string;
  customer_id: string;
  suggestion_type: "tag" | "group" | string;
  name: string;
  slug: string;
  reason: string;
  confidence: "high" | "medium" | "low" | string;
  status: "pending" | "accepted" | "rejected" | string;
  target_id: string | null;
  source: string;
  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
}

export interface ApiCRMAnalysisJob {
  id: string;
  status: string;
  total_customers: number;
  processed_customers: number;
  failed_customers: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApiCRMAnalysisStatus {
  job: ApiCRMAnalysisJob | null;
  summary: {
    total_analyzed: number;
    tags_suggested: number;
    groups_suggested: number;
    vip_customers: number;
    inactive_customers: number;
    risk_customers: number;
    high_repurchase_customers: number;
  };
  customers: Array<{
    customer_id: string;
    customer_name: string;
    email: string | null;
    phone: string | null;
    segment: string;
    churn_risk: string;
    repurchase_probability: number;
    average_ticket: number;
    tags_suggested: string[];
    groups_suggested: string[];
    confidence: string;
    next_best_action: string | null;
    generated_at: string | null;
  }>;
}

// ─── Customers ────────────────────────────────────────────────────────────────

export const customersApi = {
  list: () => get<ApiCustomer[]>("/customers"),
  get: (id: string) => get<ApiCustomer>(`/customers/${id}`),
  update: (id: string, data: { name?: string; phone?: string }) =>
    request<ApiCustomer>("PUT", `/customers/${id}`, data, customerAccessHeaders(id)),
  addAddress: (
    id: string,
    data: { label?: string; street: string; number?: string; complement?: string; neighborhood?: string; city: string; state?: string; zip_code?: string; is_default?: boolean }
  ) => request<ApiAddress>("POST", `/customers/${id}/addresses`, data, customerAccessHeaders(id)),
  deleteAddress: (customerId: string, addressId: string) =>
    request<void>("DELETE", `/customers/${customerId}/addresses/${addressId}`, undefined, customerAccessHeaders(customerId)),
  listAddresses: (id: string) =>
    request<ApiAddress[]>("GET", `/customers/${id}/addresses`, undefined, customerAccessHeaders(id)),
  getOrders: (id: string) =>
    request<ApiCustomerOrder[]>("GET", `/customers/${id}/orders`, undefined, customerAccessHeaders(id)),
  getEvents: (id: string, event_type?: string) =>
    get<ApiCustomerEvent[]>(`/customers/${id}/events${event_type ? `?event_type=${event_type}` : ""}`),
  getSummary: (id: string) => get<ApiCustomerSummary>(`/customers/${id}/summary`),
  analyzeProfile: (id: string) =>
    post<{ profile: ApiCustomerAIProfile; suggestions: ApiCustomerAISuggestion[] }>(`/customers/${id}/analyze`, {}),
  getAIProfile: (id: string) => get<ApiCustomerAIProfile | null>(`/customers/${id}/profile`),
  getAISuggestions: (id: string, status = "pending") =>
    get<ApiCustomerAISuggestion[]>(`/customers/${id}/suggestions?status=${encodeURIComponent(status)}`),
  acceptSuggestion: (suggestionId: string) =>
    post<ApiCustomerAISuggestion>(`/suggestions/${suggestionId}/accept`, {}),
  rejectSuggestion: (suggestionId: string) =>
    post<ApiCustomerAISuggestion>(`/suggestions/${suggestionId}/reject`, {}),
};

export const crmApi = {
  analyzeAllCustomers: () => post<ApiCRMAnalysisJob>("/crm/analyze-all", {}),
  getAnalysisStatus: (limit = 100) => get<ApiCRMAnalysisStatus>(`/crm/analysis/status?limit=${limit}`),
  listTags: (status = "active", search?: string) =>
    get<ApiCustomerTag[]>(`/crm/tags?status=${encodeURIComponent(status)}${search ? `&search=${encodeURIComponent(search)}` : ""}`),
  createTag: (data: { name: string; description?: string | null; color?: string; source?: string }) =>
    post<ApiCustomerTag>("/crm/tags", data),
  updateTag: (id: string, data: { name?: string; description?: string | null; color?: string; status?: string }) =>
    request<ApiCustomerTag>("PATCH", `/crm/tags/${id}`, data),
  inactiveTag: (id: string) => del<void>(`/crm/tags/${id}`),
  listCustomerTags: (customerId: string) =>
    get<ApiCustomerTag[]>(`/crm/customers/${customerId}/tags`),
  assignCustomerTag: (customerId: string, tagId: string) =>
    post<ApiCustomerTag>(`/crm/customers/${customerId}/tags/${tagId}`, {}),
  removeCustomerTag: (customerId: string, tagId: string) =>
    del<void>(`/crm/customers/${customerId}/tags/${tagId}`),
  listSegments: (status = "active") =>
    get<ApiCustomerSegment[]>(`/crm/segments?status=${encodeURIComponent(status)}`),
  createSegment: (data: { name: string; description?: string | null; rules?: ApiCustomerSegmentRule[]; source?: string }) =>
    post<ApiCustomerSegment>("/crm/segments", data),
  updateSegment: (id: string, data: { name?: string; description?: string | null; rules?: ApiCustomerSegmentRule[]; status?: string }) =>
    request<ApiCustomerSegment>("PATCH", `/crm/segments/${id}`, data),
  inactiveSegment: (id: string) => del<void>(`/crm/segments/${id}`),
  previewSegment: (id: string, limit = 50) =>
    post<ApiSegmentPreview>(`/crm/segments/${id}/preview?limit=${limit}`, {}),
  listGroups: () => get<ApiCustomerGroup[]>("/crm/groups"),
  listCustomerGroups: (customerId: string) =>
    get<ApiCustomerGroup[]>(`/crm/customers/${customerId}/groups`),
  assignCustomerGroup: (customerId: string, groupId: string) =>
    post<void>(`/crm/groups/${groupId}/members/${customerId}`, {}),
  removeCustomerGroup: (customerId: string, groupId: string) =>
    del<void>(`/crm/groups/${groupId}/members/${customerId}`),
};

// ─── Customer Events ──────────────────────────────────────────────────────────

export const customerEventsApi = {
  register: (data: {
    customer_id?: string | null;
    session_id?: string | null;
    event_type: string;
    event_name?: string;
    product_id?: string | null;
    order_id?: string | null;
    campaign_id?: string | null;
    coupon_id?: string | null;
    metadata_json?: string | null;
    source?: string | null;
    utm_source?: string | null;
    utm_medium?: string | null;
    utm_campaign?: string | null;
    device_type?: string | null;
    browser?: string | null;
    page_url?: string | null;
    referrer_url?: string | null;
  }) => request<{ id: string }>(
    "POST",
    "/customer-events",
    data,
    data.customer_id ? customerAccessHeaders(data.customer_id) : undefined,
  ),
  identify: (session_id: string, customer_id: string) =>
    request<{ updated_events: number }>(
      "POST",
      "/customer-events/identify",
      { session_id, customer_id },
      customerAccessHeaders(customer_id),
    ),
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

export const paidTrafficApi = {
  dashboard: () => get<PaidTrafficDashboard>("/paid-traffic/dashboard"),
  campaigns: () => get<TrafficCampaign[]>("/paid-traffic/campaigns"),
  createCampaign: (data: Partial<TrafficCampaign>) => post<TrafficCampaign>("/paid-traffic/campaigns", data),
  updateCampaign: (id: string, data: Partial<TrafficCampaign>) => put<TrafficCampaign>(`/paid-traffic/campaigns/${id}`, data),
  removeCampaign: (id: string) => del<void>(`/paid-traffic/campaigns/${id}`),
  links: (campaignId?: string) => get<CampaignLink[]>(`/paid-traffic/links${campaignId ? `?campaign_id=${campaignId}` : ""}`),
  createLink: (data: Partial<CampaignLink> & { campaign_id: string }) => post<CampaignLink>("/paid-traffic/links", data),
  integrations: () => get<AdIntegration[]>("/paid-traffic/integrations"),
  saveIntegration: (data: { platform: string; access_token?: string; refresh_token?: string; account_name?: string }) =>
    post<AdIntegration>("/paid-traffic/integrations", data),
  disconnectIntegration: (platform: string) => post<AdIntegration>(`/paid-traffic/integrations/${platform}/disconnect`, {}),
  syncIntegration: (platform: string) => post<{ status: string; message: string }>(`/paid-traffic/integrations/${platform}/sync`, {}),
  settings: () => get<CampaignSettings>("/paid-traffic/settings"),
  updateSettings: (data: Partial<CampaignSettings>) => put<CampaignSettings>("/paid-traffic/settings", data),
};

export const trackingApi = {
  event: (data: Record<string, unknown>) => post<{ id: string }>("/tracking/event", data),
};

export const marketingTrackApi = {
  track: (data: {
    fingerprint: string;
    session_id?: string | null;
    event_type: string;
    page?: string;
    product_id?: string;
    metadata?: Record<string, unknown>;
    utm_source?: string | null;
    utm_medium?: string | null;
    utm_campaign?: string | null;
    utm_content?: string | null;
    utm_term?: string | null;
    referrer?: string | null;
  }) => post<{ ok: boolean }>("/marketing/track", data),
};

// ─── Admin ────────────────────────────────────────────────────────────────────

export const adminApi = {
  dashboard: () => get<ApiDashboard>("/admin/dashboard"),

  getPaymentGateway: () => get<ApiPaymentGatewayConfig>("/admin/payment-gateway"),

  updatePaymentGateway: (data: ApiPaymentGatewayConfigUpdate) =>
    put<ApiPaymentGatewayConfig>("/admin/payment-gateway", data),
};

// ─── Upload ───────────────────────────────────────────────────────────────────

export const uploadApi = {
  upload: async (file: File): Promise<string> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/admin/upload`, {
      method: "POST",
      headers: { ...authHeaders() },
      body: form,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    const data = "data" in json ? json.data : json;
    return data.url as string;
  },
};

// ─── Site Config (CMS persistence) ───────────────────────────────────────────

export const siteConfigApi = {
  get: async (): Promise<Record<string, unknown>> => {
    const res = await fetch(`${BASE}/site-config`);
    if (!res.ok) return {};
    const json = await res.json();
    return (json?.data ?? json) as Record<string, unknown>;
  },
  save: (content: unknown): Promise<unknown> =>
    put("/admin/site-config", content),
};

// ─── Delivery / Logistics ─────────────────────────────────────────────────────

export interface DeliveryPerson {
  id: string;
  name: string;
  phone: string;
  vehicle_type: "motorcycle" | "bicycle" | "car" | "walking";
  status: "available" | "busy" | "offline";
  active: boolean;
  email?: string;
  cpf?: string;
  cnh?: string;
  pix_key?: string;
  total_deliveries: number;
  average_rating: number;
  location_lat?: number;
  location_lng?: number;
  location_updated_at?: string;
  created_at: string;
}

export interface OrderAddress {
  id: string;
  delivery_name?: string;
  delivery_phone?: string;
  delivery_street?: string;
  delivery_city?: string;
  delivery_complement?: string;
}

export interface DeliveryRecord {
  id: string;
  order_id: string;
  delivery_person_id?: string;
  status: string;
  assigned_at?: string;
  picked_up_at?: string;
  delivered_at?: string;
  estimated_minutes: number;
  confirmation_code?: string;
  confirmed_by_code_at?: string;
  rating?: number;
  rating_comment?: string;
  created_at: string;
  updated_at: string;
  order?: OrderAddress;
}

export interface PersonOnDuty {
  person: DeliveryPerson;
  active_deliveries: DeliveryRecord[];
}

export interface LogisticsOverview {
  persons_on_duty: PersonOnDuty[];
  total_active: number;
}

export interface LogisticsSettings {
  id: string;
  auto_assign: boolean;
  max_concurrent_deliveries: number;
  default_estimated_minutes: number;
  confirmation_code_enabled: boolean;
  rate_per_delivery: number;
  updated_at?: string;
}

// ── Phase 3 types ─────────────────────────────────────────────────────────────

export interface DeliveryEarning {
  id: string;
  delivery_id: string;
  delivery_person_id: string;
  person_name?: string;
  person_phone?: string;
  amount: number;
  status: "pending" | "paid";
  period_date?: string;
  paid_at?: string;
  paid_by?: string;
  notes?: string;
  created_at?: string;
}

export interface DriverAnalytics {
  person_id: string;
  person_name: string;
  person_phone: string;
  vehicle_type: string;
  total_deliveries: number;
  avg_duration_minutes: number | null;
  avg_rating: number | null;
  completion_rate: number;
  pending_earnings: number;
  paid_earnings: number;
}

export interface DeliveryAlert {
  id: string;
  order_id: string;
  delivery_person_id: string | null;
  person_name: string | null;
  person_phone: string | null;
  status: string;
  assigned_at: string | null;
  estimated_minutes: number;
  overdue_minutes: number;
  delivery_street?: string | null;
}

function driverAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("driver_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function driverRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...driverAuthHeaders() },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const json = await res.json();
  return ("data" in json ? json.data : json) as T;
}

export const deliveryApi = {
  // Admin — delivery persons
  listPersons: (options: boolean | { availableOnly?: boolean; includeInactive?: boolean } = false) => {
    const availableOnly = typeof options === "boolean" ? options : !!options.availableOnly;
    const includeInactive = typeof options === "boolean" ? false : !!options.includeInactive;
    const qs = new URLSearchParams();
    if (availableOnly) qs.set("available_only", "true");
    if (includeInactive) qs.set("include_inactive", "true");
    const q = qs.toString();
    return get<DeliveryPerson[]>(`/delivery/persons${q ? `?${q}` : ""}`);
  },
  createPerson: (body: Record<string, unknown>) =>
    post<DeliveryPerson>("/delivery/persons", body),
  updatePerson: (id: string, body: Record<string, unknown>) =>
    put<DeliveryPerson>(`/delivery/persons/${id}`, body),
  setPersonStatus: (id: string, status: "available" | "offline") =>
    put<DeliveryPerson>(`/delivery/persons/${id}/status`, { status }),
  setPersonAccess: (id: string, active: boolean) =>
    put<DeliveryPerson>(`/delivery/persons/${id}/access`, { active }),
  deactivatePerson: (id: string) =>
    del<void>(`/delivery/persons/${id}`),

  // Admin — deliveries
  assign: (order_id: string, delivery_person_id: string, estimated_minutes = 40) =>
    post<DeliveryRecord>("/delivery/assign", { order_id, delivery_person_id, estimated_minutes }),
  listActive: () =>
    get<DeliveryRecord[]>("/delivery/active"),

  // Admin — settings
  getSettings: () =>
    get<LogisticsSettings>("/delivery/settings"),
  updateSettings: (body: Partial<LogisticsSettings>) =>
    put<LogisticsSettings>("/delivery/settings", body),

  // Admin — map overview
  getOverview: () =>
    get<LogisticsOverview>("/delivery/overview"),

  // Driver app
  driverLogin: (email: string, password: string) =>
    driverRequest<{ token: string; person: DeliveryPerson }>("POST", "/delivery/driver/login", { email, password }),
  driverMe: () =>
    driverRequest<DeliveryPerson>("GET", "/delivery/driver/me"),
  driverDeliveries: () =>
    driverRequest<DeliveryRecord[]>("GET", "/delivery/driver/deliveries"),
  driverUpdateLocation: (lat: number, lng: number) =>
    driverRequest<DeliveryPerson>("PUT", "/delivery/driver/location", { lat, lng }),

  // Confirm delivery (public — no auth needed)
  confirmCode: (deliveryId: string, code: string) =>
    driverRequest<DeliveryRecord>("POST", `/delivery/${deliveryId}/confirm-code`, { code }),

  // Admin — Phase 3: earnings
  listEarnings: (params?: { person_id?: string; status?: string; period_from?: string; period_to?: string }) => {
    const qs = new URLSearchParams();
    if (params?.person_id) qs.set("person_id", params.person_id);
    if (params?.status) qs.set("status", params.status);
    if (params?.period_from) qs.set("period_from", params.period_from);
    if (params?.period_to) qs.set("period_to", params.period_to);
    const q = qs.toString();
    return get<DeliveryEarning[]>(`/delivery/earnings${q ? `?${q}` : ""}`);
  },
  payEarnings: (earning_ids: string[], paid_by = "admin") =>
    post<{ paid: number }>("/delivery/earnings/pay", { earning_ids, paid_by }),

  // Admin — Phase 3: analytics
  getAnalytics: (params?: { period_from?: string; period_to?: string; person_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.period_from) qs.set("period_from", params.period_from);
    if (params?.period_to) qs.set("period_to", params.period_to);
    if (params?.person_id) qs.set("person_id", params.person_id);
    const q = qs.toString();
    return get<DriverAnalytics[]>(`/delivery/analytics${q ? `?${q}` : ""}`);
  },

  // Admin — Phase 3: delay alerts
  getAlerts: () => get<DeliveryAlert[]>("/delivery/alerts"),

  // Admin — Phase 4: auto-assignment
  autoAssign: () =>
    post<Array<{ order_id: string; delivery_id: string; person_name: string }>>("/delivery/auto-assign", {}),

  // Admin — Phase 4: geocoding proxy (Nominatim, cached in DB)
  geocode: (q: string) =>
    get<{ lat: number | null; lng: number | null; cached: boolean }>(
      `/delivery/geocode?q=${encodeURIComponent(q)}`
    ),
};
