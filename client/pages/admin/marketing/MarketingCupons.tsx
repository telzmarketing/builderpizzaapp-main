import { useEffect, useState, useRef } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, Tag, CheckCircle,
  XCircle, Clock, RefreshCw, BarChart2, List,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (j: any) => j?.data ?? j;

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
  expiry_date?: string;
  active: boolean;
  campaign_id?: string;
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
  expiry_date: string;
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
  expiry_date: "",
  active: true,
});

function fmtDiscount(c: Coupon) {
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

export default function MarketingCupons() {
  const [tab, setTab] = useState<Tab>("cupons");
  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  // ── Cupons ──
  const [coupons, setCoupons] = useState<Coupon[]>([]);
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
    fetch(`${BASE}/coupons`, { headers })
      .then(r => r.json())
      .then(d => setCoupons(Array.isArray(d) ? d : (unwrap(d) ?? [])))
      .catch(() => setError("Falha ao carregar cupons."))
      .finally(() => setLoading(false));
  };

  const fetchUsage = () => {
    setUsageLoading(true);
    fetch(`${BASE}/coupons/usage`, { headers })
      .then(r => r.json())
      .then(d => setUsage(Array.isArray(d) ? d : (unwrap(d) ?? [])))
      .catch(() => setUsage([]))
      .finally(() => setUsageLoading(false));
  };

  useEffect(() => {
    if (tab === "cupons") fetchCoupons();
    if (tab === "uso")    fetchUsage();
  }, [tab]); // eslint-disable-line

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
      expiry_date: c.expiry_date ? c.expiry_date.slice(0, 16) : "",
      active: c.active,
    });
    setShowModal(true);
  };

  const saveCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.code.trim()) { alert("Código obrigatório."); return; }
    if (!form.discount_value || Number(form.discount_value) <= 0) { alert("Valor de desconto deve ser maior que zero."); return; }

    setSaving(true);
    try {
      const payload = {
        code: form.code.toUpperCase().trim(),
        description: form.description || null,
        icon: form.icon || "🎟️",
        coupon_type: form.coupon_type,
        discount_value: Number(form.discount_value),
        min_order_value: Number(form.min_order_value) || 0,
        max_uses: form.max_uses !== "" ? Number(form.max_uses) : null,
        max_uses_per_customer: form.max_uses_per_customer !== "" ? Number(form.max_uses_per_customer) : null,
        expiry_date: form.expiry_date ? new Date(form.expiry_date).toISOString() : null,
        active: form.active,
      };

      const url = editingId ? `${BASE}/coupons/${editingId}` : `${BASE}/coupons`;
      const method = editingId ? "PUT" : "POST";
      const r = await fetch(url, { method, headers, body: JSON.stringify(payload) });

      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err?.detail ?? "Erro ao salvar cupom.");
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
    await fetch(`${BASE}/coupons/${c.id}`, {
      method: "PUT", headers,
      body: JSON.stringify({ active: !c.active }),
    });
    fetchCoupons();
  };

  const deleteCoupon = async (id: string) => {
    if (!confirm("Excluir este cupom?")) return;
    await fetch(`${BASE}/coupons/${id}`, { method: "DELETE", headers });
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
                  <input type="number" min="0.01" step="0.01" value={form.discount_value}
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
