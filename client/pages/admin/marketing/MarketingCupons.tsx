import { useEffect, useState, useRef } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, Tag, CheckCircle,
  XCircle, Clock, RefreshCw, BarChart2, List, Truck, Gift,
  Zap,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  couponsApi,
  marketingAutomationsApi,
  productsApi,
  type ApiMarketingAutomation,
  type ApiProduct,
} from "@/lib/api";

type Tab = "cupons" | "uso";

interface Coupon {
  id: string;
  code: string;
  description?: string;
  icon: string;
  coupon_type: "percentage" | "fixed";
  discount_value: number;
  min_order_value: number;
  max_uses?: number;
  max_uses_per_customer?: number;
  used_count: number;
  starts_at?: string;
  ends_at?: string;
  expiry_date?: string;
  free_shipping?: boolean;
  gift_enabled?: boolean;
  gift_product_id?: string | null;
  gift_quantity?: number;
  stackable?: boolean;
  public_profile?: boolean;
  active: boolean;
  campaign_id?: string;
  trigger_automation_id?: string | null;
  created_at: string;
}

type CouponForm = {
  code: string;
  description: string;
  icon: string;
  coupon_type: Coupon["coupon_type"];
  discount_value: number;
  min_order_value: number;
  max_uses: string | number;
  max_uses_per_customer: string | number;
  starts_at: string;
  ends_at: string;
  expiry_date: string;
  free_shipping: boolean;
  gift_enabled: boolean;
  gift_product_id: string;
  gift_quantity: number;
  stackable: boolean;
  public_profile: boolean;
  trigger_automation_id: string;
  active: boolean;
};

interface UsageRow {
  id: string;
  coupon_id: string;
  customer_id?: string;
  phone?: string;
  order_id?: string;
  created_at: string;
}

const IC = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

const emptyForm = (): CouponForm => ({
  code: "",
  description: "",
  icon: "🎟️",
  coupon_type: "percentage",
  discount_value: 10,
  min_order_value: 0,
  max_uses: "" as string | number,
  max_uses_per_customer: "" as string | number,
  starts_at: "",
  ends_at: "",
  expiry_date: "",
  free_shipping: false,
  gift_enabled: false,
  gift_product_id: "",
  gift_quantity: 1,
  stackable: false,
  public_profile: false,
  trigger_automation_id: "",
  active: true,
});

function fmtDiscount(c: Coupon) {
  if (!c.discount_value || c.discount_value <= 0) return "Sem desconto";
  return c.coupon_type === "percentage"
    ? `${c.discount_value}% OFF`
    : `R$ ${c.discount_value.toFixed(2).replace(".", ",")} OFF`;
}

function fmtDate(s?: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function fmtDateShort(s?: string | null) {
  if (!s) return "Sem vencimento";
  return new Date(s).toLocaleDateString("pt-BR");
}

function isExpired(c: Coupon) {
  if (!c.expiry_date) return false;
  return new Date(c.expiry_date) < new Date();
}

function automationLabel(a: ApiMarketingAutomation) {
  const trigger = a.trigger_value ? `${a.trigger} (${a.trigger_value})` : a.trigger;
  return `${a.name} - ${trigger}`;
}

export default function MarketingCupons() {
  const [tab, setTab] = useState<Tab>("cupons");
  // ── Cupons ──
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [automations, setAutomations] = useState<ApiMarketingAutomation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "active" | "inactive" | "expired">("all");

  // ── Modal ──
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);

  // ── Uso ──
  const [usage, setUsage] = useState<UsageRow[]>([]);
  const [usageLoading, setUsageLoading] = useState(false);
  const usageRef = useRef<ReturnType<typeof setInterval>>(null);

  // ── Fetchers ──
  const fetchCoupons = () => {
    setLoading(true); setError("");
    couponsApi.list()
      .then(d => setCoupons(d ?? []))
      .catch(() => setError("Falha ao carregar cupons."))
      .finally(() => setLoading(false));
  };

  const fetchUsage = () => {
    setUsageLoading(true);
    couponsApi.listUsage()
      .then(d => setUsage(d ?? []))
      .catch(() => setUsage([]))
      .finally(() => setUsageLoading(false));
  };

  useEffect(() => {
    if (tab === "cupons") fetchCoupons();
    if (tab === "uso")    fetchUsage();
  }, [tab]); // eslint-disable-line

  useEffect(() => {
    productsApi.list(false)
      .then(setProducts)
      .catch(() => setProducts([]));
    marketingAutomationsApi.list()
      .then(setAutomations)
      .catch(() => setAutomations([]));
  }, []);

  useEffect(() => {
    if (tab === "uso") {
      usageRef.current = setInterval(fetchUsage, 30000);
    } else {
      if (usageRef.current) clearInterval(usageRef.current);
    }
    return () => { if (usageRef.current) clearInterval(usageRef.current); };
  }, [tab]); // eslint-disable-line

  // ── Filtered list ──
  const filtered = coupons.filter(c => {
    if (filter === "active")   return c.active && !isExpired(c);
    if (filter === "inactive") return !c.active;
    if (filter === "expired")  return isExpired(c);
    return true;
  });

  // ── CRUD ──
  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowModal(true);
  };

  const openEdit = (c: Coupon) => {
    setEditingId(c.id);
    setForm({
      code: c.code,
      description: c.description ?? "",
      icon: c.icon,
      coupon_type: c.coupon_type,
      discount_value: c.discount_value,
      min_order_value: c.min_order_value,
      max_uses: c.max_uses ?? "",
      max_uses_per_customer: c.max_uses_per_customer ?? "",
      starts_at: c.starts_at ? c.starts_at.slice(0, 16) : "",
      ends_at: c.ends_at ? c.ends_at.slice(0, 16) : "",
      expiry_date: c.expiry_date ? c.expiry_date.slice(0, 16) : "",
      free_shipping: !!c.free_shipping,
      gift_enabled: !!c.gift_enabled,
      gift_product_id: c.gift_product_id ?? "",
      gift_quantity: c.gift_quantity || 1,
      stackable: !!c.stackable,
      public_profile: !!c.public_profile,
      trigger_automation_id: c.trigger_automation_id ?? "",
      active: c.active,
    });
    setShowModal(true);
  };

  const saveCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.code.trim()) { alert("Código obrigatório."); return; }
    const discountValue = Number(form.discount_value) || 0;
    if (discountValue <= 0 && !form.free_shipping && !form.gift_enabled) { alert("Informe desconto, frete gratis ou produto brinde."); return; }
    if (form.gift_enabled && !form.gift_product_id) { alert("Selecione o produto brinde."); return; }

    setSaving(true);
    try {
      const payload = {
        code: form.code.toUpperCase().trim(),
        description: form.description || null,
        icon: form.icon || "🎟️",
        coupon_type: form.coupon_type,
        discount_value: discountValue,
        min_order_value: Number(form.min_order_value) || 0,
        max_uses: form.max_uses !== "" ? Number(form.max_uses) : null,
        max_uses_per_customer: form.max_uses_per_customer !== "" ? Number(form.max_uses_per_customer) : null,
        starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
        expiry_date: form.expiry_date ? new Date(form.expiry_date).toISOString() : null,
        free_shipping: form.free_shipping,
        gift_enabled: form.gift_enabled,
        gift_product_id: form.gift_enabled && form.gift_product_id ? form.gift_product_id : null,
        gift_quantity: Math.max(1, Number(form.gift_quantity) || 1),
        stackable: form.stackable,
        public_profile: form.public_profile,
        trigger_automation_id: form.trigger_automation_id || null,
        active: form.active,
      };

      if (editingId) {
        await couponsApi.update(editingId, payload);
      } else {
        await couponsApi.create(payload);
      }
      setShowModal(false);
      fetchCoupons();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (c: Coupon) => {
    await couponsApi.update(c.id, { active: !c.active });
    fetchCoupons();
  };

  const deleteCoupon = async (id: string) => {
    if (!confirm("Excluir este cupom?")) return;
    await couponsApi.remove(id);
    fetchCoupons();
  };

  const TABS_CFG: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "cupons", label: "Cupons", icon: Tag },
    { id: "uso",    label: "Histórico de Uso", icon: List },
  ];

  const FILTER_TABS = [
    { id: "all" as const,      label: "Todos" },
    { id: "active" as const,   label: "Ativos" },
    { id: "inactive" as const, label: "Inativos" },
    { id: "expired" as const,  label: "Expirados" },
  ];

  const brindesDisponiveis = products.filter(p => (p as any).product_type === "brinde" && p.active);
  const automationById = new Map(automations.map(a => [a.id, a]));

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Cupons de Desconto</h1>
          </div>
          <div className="flex items-center gap-3">
            {tab === "cupons" && (
              <button onClick={openCreate}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                <Plus size={16} /> Novo Cupom
              </button>
            )}
            {tab === "uso" && (
              <button onClick={fetchUsage}
                className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors">
                <RefreshCw size={16} />
              </button>
            )}
            <AdminTopActions />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-1 bg-surface-02 border border-surface-03 rounded-xl p-1">
          {TABS_CFG.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === id ? "bg-gold text-black" : "text-stone hover:text-cream hover:bg-surface-03"}`}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {/* ═══ CUPONS ═══ */}
        {tab === "cupons" && (
          <>
            {/* Stats bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: "Total",    value: coupons.length,                             cls: "text-cream" },
                { label: "Ativos",   value: coupons.filter(c => c.active && !isExpired(c)).length, cls: "text-green-400" },
                { label: "Inativos", value: coupons.filter(c => !c.active).length,      cls: "text-red-400" },
                { label: "Expirados",value: coupons.filter(isExpired).length,           cls: "text-orange-400" },
              ].map(m => (
                <div key={m.label} className="bg-surface-02 border border-surface-03 rounded-2xl p-4">
                  <p className="text-xs text-stone mb-1">{m.label}</p>
                  <p className={`text-2xl font-bold ${m.cls}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Filter pills */}
            <div className="flex flex-wrap gap-2">
              {FILTER_TABS.map(f => (
                <button key={f.id} onClick={() => setFilter(f.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    filter === f.id ? "bg-gold text-black" : "bg-surface-02 border border-surface-03 text-stone hover:text-cream"}`}>
                  {f.label}
                </button>
              ))}
            </div>

            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>
            )}

            {loading ? (
              <div className="flex justify-center py-16"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center py-20 bg-surface-02 border border-surface-03 rounded-2xl">
                <Tag size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum cupom encontrado.</p>
                <button onClick={openCreate}
                  className="mt-4 flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors">
                  <Plus size={14} /> Criar Cupom
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {filtered.map(c => {
                  const expired = isExpired(c);
                  const triggerAutomation = c.trigger_automation_id ? automationById.get(c.trigger_automation_id) : null;
                  return (
                    <div key={c.id}
                      className={`bg-surface-02 border rounded-2xl p-4 space-y-3 flex flex-col transition-opacity ${
                        !c.active || expired ? "opacity-60 border-surface-03" : "border-surface-03 hover:border-gold/30"}`}>

                      {/* Top row */}
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="text-2xl flex-shrink-0">{c.icon}</span>
                          <div className="min-w-0">
                            <p className="text-cream font-bold text-sm font-mono tracking-widest truncate">{c.code}</p>
                            <p className="text-stone text-xs truncate">{c.description ?? "—"}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1 shrink-0">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                            c.coupon_type === "percentage" ? "bg-gold/20 text-gold" : "bg-green-500/20 text-green-400"}`}>
                            {fmtDiscount(c)}
                          </span>
                          {expired ? (
                            <span className="text-xs px-1.5 py-0.5 rounded-full bg-orange-500/20 text-orange-400">Expirado</span>
                          ) : c.active ? (
                            <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-500/20 text-green-400">Ativo</span>
                          ) : (
                            <span className="text-xs px-1.5 py-0.5 rounded-full bg-surface-03 text-stone">Inativo</span>
                          )}
                        </div>
                      </div>

                      {(c.free_shipping || c.gift_enabled || c.stackable || c.public_profile) && (
                        <div className="flex flex-wrap gap-1">
                          {c.public_profile && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-gold/15 px-2 py-0.5 text-xs text-gold">
                              <Tag size={11} /> Perfil do cliente
                            </span>
                          )}
                          {c.free_shipping && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/15 px-2 py-0.5 text-xs text-blue-300">
                              <Truck size={11} /> Frete gratis
                            </span>
                          )}
                          {c.gift_enabled && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-2 py-0.5 text-xs text-green-300">
                              <Gift size={11} /> Brinde{c.gift_quantity ? ` x${c.gift_quantity}` : ""}
                            </span>
                          )}
                          {c.stackable && (
                            <span className="rounded-full bg-surface-03 px-2 py-0.5 text-xs text-stone">Combinavel</span>
                          )}
                        </div>
                      )}

                      {c.trigger_automation_id && (
                        <div className="inline-flex max-w-full items-center gap-1 rounded-full bg-purple-500/15 px-2 py-1 text-xs text-purple-300">
                          <Zap size={11} />
                          <span className="truncate">
                            {triggerAutomation ? automationLabel(triggerAutomation) : "Gatilho vinculado"}
                          </span>
                        </div>
                      )}

                      {/* Details */}
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-stone">
                        {c.min_order_value > 0 && (
                          <span>Mín: <span className="text-cream">R$ {c.min_order_value.toFixed(2).replace(".", ",")}</span></span>
                        )}
                        <span>Usos: <span className="text-cream">{c.used_count}{c.max_uses ? `/${c.max_uses}` : ""}</span></span>
                        {c.max_uses_per_customer && (
                          <span>Por cliente: <span className="text-cream">{c.max_uses_per_customer}</span></span>
                        )}
                        <span>Validade: <span className={expired ? "text-orange-400" : "text-cream"}>{fmtDateShort(c.expiry_date)}</span></span>
                      </div>

                      {/* Progress bar */}
                      {c.max_uses && (
                        <div className="space-y-1">
                          <div className="h-1.5 bg-surface-03 rounded-full overflow-hidden">
                            <div className="h-full bg-gold rounded-full transition-all"
                              style={{ width: `${Math.min((c.used_count / c.max_uses) * 100, 100)}%` }} />
                          </div>
                          <p className="text-[10px] text-stone text-right">{Math.round((c.used_count / c.max_uses) * 100)}% utilizado</p>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex items-center gap-2 pt-1">
                        <button onClick={() => toggleActive(c)}
                          className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                            c.active ? "bg-surface-03 text-stone hover:bg-red-500/10 hover:text-red-400"
                                     : "bg-surface-03 text-stone hover:bg-green-500/10 hover:text-green-400"}`}>
                          {c.active ? "Desativar" : "Ativar"}
                        </button>
                        <button onClick={() => openEdit(c)}
                          className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors">
                          <Pencil size={14} />
                        </button>
                        <button onClick={() => deleteCoupon(c.id)}
                          className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ═══ USO ═══ */}
        {tab === "uso" && (
          <>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <p className="text-stone text-sm">Atualização automática a cada 30s</p>
            </div>
            {usageLoading ? (
              <div className="flex justify-center py-16"><Loader2 className="animate-spin text-gold" size={28} /></div>
            ) : (
              <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
                {usage.length === 0 ? (
                  <div className="flex flex-col items-center py-16">
                    <BarChart2 size={40} className="text-surface-03 mb-3" />
                    <p className="text-stone text-sm">Nenhum uso registrado ainda.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                          {["Cupom", "Cliente", "Telefone", "Pedido", "Data/Hora"].map(h => (
                            <th key={h} className="text-left p-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-03">
                        {usage.map(u => {
                          const coupon = coupons.find(c => c.id === u.coupon_id);
                          return (
                            <tr key={u.id} className="hover:bg-surface-03/30 transition-colors">
                              <td className="p-3">
                                <span className="font-mono text-xs font-semibold text-gold">
                                  {coupon?.code ?? u.coupon_id.slice(0, 8)}
                                </span>
                              </td>
                              <td className="p-3 text-stone text-xs font-mono">
                                {u.customer_id ? u.customer_id.slice(0, 8) + "…" : "—"}
                              </td>
                              <td className="p-3 text-stone text-xs">{u.phone ?? "—"}</td>
                              <td className="p-3 text-stone text-xs font-mono">
                                {u.order_id ? u.order_id.slice(0, 8) + "…" : "—"}
                              </td>
                              <td className="p-3 text-stone text-xs whitespace-nowrap">{fmtDate(u.created_at)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>

      {/* ── Modal Criar / Editar ── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-surface-03">
              <h2 className="text-cream font-semibold">{editingId ? "Editar Cupom" : "Novo Cupom"}</h2>
              <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={saveCoupon} className="p-5 space-y-4">

              {/* Código + Ícone */}
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2 space-y-1">
                  <label className="text-xs text-stone">Código *</label>
                  <input type="text" value={form.code}
                    onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    placeholder="EX: PIZZA20" className={`${IC} font-mono tracking-widest uppercase`} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Ícone</label>
                  <input type="text" value={form.icon}
                    onChange={e => setForm(f => ({ ...f, icon: e.target.value }))}
                    placeholder="🎟️" className={`${IC} text-xl text-center`} />
                </div>
              </div>

              {/* Descrição */}
              <div className="space-y-1">
                <label className="text-xs text-stone">Descrição</label>
                <input type="text" value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Ex: 20% de desconto em qualquer pizza" className={IC} />
              </div>

              {/* Tipo + Valor */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Tipo *</label>
                  <select value={form.coupon_type}
                    onChange={e => setForm(f => ({ ...f, coupon_type: e.target.value as "percentage" | "fixed" }))}
                    className={IC}>
                    <option value="percentage">Percentual (%)</option>
                    <option value="fixed">Valor Fixo (R$)</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">
                    {form.coupon_type === "percentage" ? "Desconto (%) *" : "Desconto (R$) *"}
                  </label>
                  <input type="number" min="0" step="0.01" value={form.discount_value}
                    onChange={e => setForm(f => ({ ...f, discount_value: +e.target.value }))}
                    className={IC} />
                </div>
              </div>

              {/* Pedido mínimo + Usos totais + Por cliente */}
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Pedido mínimo (R$)</label>
                  <input type="number" min="0" step="0.01" value={form.min_order_value}
                    onChange={e => setForm(f => ({ ...f, min_order_value: +e.target.value }))}
                    placeholder="0" className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Usos totais</label>
                  <input type="number" min="1" step="1" value={form.max_uses}
                    onChange={e => setForm(f => ({ ...f, max_uses: e.target.value }))}
                    placeholder="Ilimitado" className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Por cliente</label>
                  <input type="number" min="1" step="1" value={form.max_uses_per_customer}
                    onChange={e => setForm(f => ({ ...f, max_uses_per_customer: e.target.value }))}
                    placeholder="Ilimitado" className={IC} />
                </div>
              </div>

              {/* Validade */}
              <div className="space-y-1">
                <label className="text-xs text-stone">Validade (opcional)</label>
                <input type="datetime-local" value={form.expiry_date}
                  onChange={e => setForm(f => ({ ...f, expiry_date: e.target.value }))}
                  className={IC} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Inicio (opcional)</label>
                  <input type="datetime-local" value={form.starts_at}
                    onChange={e => setForm(f => ({ ...f, starts_at: e.target.value }))}
                    className={IC} />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-stone">Fim (opcional)</label>
                  <input type="datetime-local" value={form.ends_at}
                    onChange={e => setForm(f => ({ ...f, ends_at: e.target.value }))}
                    className={IC} />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs text-stone">Gatilho de cliente</label>
                <select value={form.trigger_automation_id}
                  onChange={e => setForm(f => ({ ...f, trigger_automation_id: e.target.value }))}
                  className={IC}>
                  <option value="">Sem gatilho</option>
                  {automations.map(a => (
                    <option key={a.id} value={a.id}>{automationLabel(a)}</option>
                  ))}
                </select>
              </div>

              <div className="rounded-xl border border-surface-03 bg-surface-03/30 p-4 space-y-3">
                <p className="text-sm font-semibold text-cream">Beneficios compostos</p>

                <button type="button"
                  onClick={() => setForm(f => ({ ...f, free_shipping: !f.free_shipping }))}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-sm transition-colors ${
                    form.free_shipping ? "border-gold bg-gold/10 text-gold" : "border-surface-03 bg-surface-02 text-stone hover:text-cream"}`}>
                  <span className="flex items-center gap-2"><Truck size={16} /> Aplicar frete gratis</span>
                  <span className={`h-5 w-9 rounded-full p-0.5 transition-colors ${form.free_shipping ? "bg-gold" : "bg-surface-03"}`}>
                    <span className={`block h-4 w-4 rounded-full bg-white transition-transform ${form.free_shipping ? "translate-x-4" : ""}`} />
                  </span>
                </button>

                <button type="button"
                  onClick={() => setForm(f => ({ ...f, gift_enabled: !f.gift_enabled }))}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-sm transition-colors ${
                    form.gift_enabled ? "border-gold bg-gold/10 text-gold" : "border-surface-03 bg-surface-02 text-stone hover:text-cream"}`}>
                  <span className="flex items-center gap-2"><Gift size={16} /> Adicionar produto brinde</span>
                  <span className={`h-5 w-9 rounded-full p-0.5 transition-colors ${form.gift_enabled ? "bg-gold" : "bg-surface-03"}`}>
                    <span className={`block h-4 w-4 rounded-full bg-white transition-transform ${form.gift_enabled ? "translate-x-4" : ""}`} />
                  </span>
                </button>

                {form.gift_enabled && (
                  <div className="grid grid-cols-3 gap-3">
                    <div className="col-span-2 space-y-1">
                      <label className="text-xs text-stone">Brinde *</label>
                      <select value={form.gift_product_id}
                        onChange={e => setForm(f => ({ ...f, gift_product_id: e.target.value }))}
                        className={IC}>
                        <option value="">Selecione um brinde</option>
                        {brindesDisponiveis.length === 0 && (
                          <option disabled value="">Nenhum brinde cadastrado</option>
                        )}
                        {brindesDisponiveis.map(p => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-stone">Qtd.</label>
                      <input type="number" min="1" step="1" value={form.gift_quantity}
                        onChange={e => setForm(f => ({ ...f, gift_quantity: Math.max(1, Number(e.target.value) || 1) }))}
                        className={IC} />
                    </div>
                  </div>
                )}

                <label className="flex items-center gap-2 text-sm text-stone">
                  <input type="checkbox" checked={form.stackable}
                    onChange={e => setForm(f => ({ ...f, stackable: e.target.checked }))}
                    className="h-4 w-4 accent-gold" />
                  Permitir combinar com outros beneficios
                </label>

                <label className="flex items-center gap-2 text-sm text-stone">
                  <input type="checkbox" checked={form.public_profile}
                    onChange={e => setForm(f => ({ ...f, public_profile: e.target.checked }))}
                    className="h-4 w-4 accent-gold" />
                  Aparecer no perfil dos clientes
                </label>
              </div>

              {/* Ativo */}
              <div className="flex items-center gap-3">
                <button type="button"
                  onClick={() => setForm(f => ({ ...f, active: !f.active }))}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${form.active ? "bg-gold" : "bg-surface-03"}`}>
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${form.active ? "translate-x-6" : "translate-x-1"}`} />
                </button>
                <span className="text-sm text-cream">{form.active ? "Cupom ativo" : "Cupom inativo"}</span>
              </div>

              {/* Buttons */}
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)}
                  className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm transition-colors">
                  Cancelar
                </button>
                <button type="submit" disabled={saving}
                  className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm disabled:opacity-60 flex items-center justify-center gap-2 transition-colors">
                  {saving && <Loader2 size={14} className="animate-spin" />}
                  {editingId ? "Salvar" : "Criar Cupom"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
