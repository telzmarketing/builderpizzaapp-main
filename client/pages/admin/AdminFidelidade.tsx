import { useEffect, useState } from "react";
import {
  Trophy, Plus, Trash2, Edit2, Save, X, Users, Star,
  RefreshCw, Gift, ChevronDown, ChevronUp, ArrowUpDown,
  Layers, Coins,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import {
  loyaltyApi,
  ApiLoyaltyLevel, ApiLoyaltyBenefit, ApiLoyaltyReward,
  ApiCustomerLoyalty,
} from "@/lib/api";

// ── Color palette (keep class names literal for Tailwind JIT) ────────────────
const colorPalette: Record<string, { label: string; preview: string; text: string }> = {
  orange: { label: "Laranja", preview: "bg-orange-400",  text: "text-orange-400" },
  gray:   { label: "Prata",   preview: "bg-slate-300",   text: "text-parchment" },
  yellow: { label: "Ouro",    preview: "bg-yellow-400",  text: "text-yellow-400" },
  blue:   { label: "Azul",    preview: "bg-blue-400",    text: "text-blue-400" },
  green:  { label: "Verde",   preview: "bg-green-400",   text: "text-green-400" },
  purple: { label: "Roxo",    preview: "bg-purple-400",  text: "text-purple-400" },
};

const BENEFIT_TYPE_LABELS: Record<string, string> = {
  product: "Produto Grátis",
  discount: "Desconto %",
  frete_gratis: "Frete Grátis",
  experience: "Experiência",
};

type Tab = "levels" | "benefits" | "customers" | "points";

export default function AdminFidelidade() {
  const [tab, setTab] = useState<Tab>("levels");
  const [levels, setLevels] = useState<ApiLoyaltyLevel[]>([]);
  const [benefits, setBenefits] = useState<ApiLoyaltyBenefit[]>([]);
  const [rewards, setRewards] = useState<ApiLoyaltyReward[]>([]);
  const [customers, setCustomers] = useState<ApiCustomerLoyalty[]>([]);
  const [filterLevel, setFilterLevel] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Level form
  const [showLevelForm, setShowLevelForm] = useState(false);
  const [editingLevelId, setEditingLevelId] = useState<string | null>(null);
  const [levelForm, setLevelForm] = useState({ name: "", min_points: 0, max_points: "", icon: "🥉", color: "orange" });

  // Benefit form
  const [showBenefitForm, setShowBenefitForm] = useState(false);
  const [editingBenefitId, setEditingBenefitId] = useState<string | null>(null);
  const [benefitForm, setBenefitForm] = useState({
    level_id: "", benefit_type: "discount" as ApiLoyaltyBenefit["benefit_type"],
    label: "", description: "", value: 0, min_order_value: 0,
    expires_in_days: "", usage_limit: 1, stackable: false, active: true,
  });

  // Point adjustment
  const [pointsForm, setPointsForm] = useState({ customer_id: "", points: 0, description: "Ajuste manual" });
  const [expandedCustomer, setExpandedCustomer] = useState<string | null>(null);

  // Reward form
  const [showRewardForm, setShowRewardForm] = useState(false);
  const [rewardForm, setRewardForm] = useState({ label: "", points_required: 100, icon: "🎁", active: true });

  useEffect(() => { loadAll(); }, []);
  useEffect(() => {
    if (tab === "customers") loadCustomers();
  }, [tab, filterLevel]);

  async function loadAll() {
    setLoading(true);
    try {
      const [lvls, bens, rwds] = await Promise.all([
        loyaltyApi.levels(),
        loyaltyApi.benefits(),
        loyaltyApi.rewards(),
      ]);
      setLevels(lvls);
      setBenefits(bens);
      setRewards(rwds);
    } catch { setError("Erro ao carregar dados de fidelidade."); }
    finally { setLoading(false); }
  }

  async function loadCustomers() {
    try {
      const data = await loyaltyApi.adminCustomers(filterLevel || undefined);
      setCustomers(data);
    } catch { setError("Erro ao carregar clientes."); }
  }

  function flash(msg: string) {
    setSuccess(msg);
    setTimeout(() => setSuccess(""), 3000);
  }

  // ── Level CRUD ────────────────────────────────────────────────────────────────

  async function saveLevel(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: levelForm.name,
        min_points: levelForm.min_points,
        max_points: levelForm.max_points ? Number(levelForm.max_points) : null,
        icon: levelForm.icon,
        color: levelForm.color,
      } as Omit<ApiLoyaltyLevel, "id">;
      if (editingLevelId) {
        const updated = await loyaltyApi.updateLevel(editingLevelId, payload);
        setLevels(levels.map(l => l.id === editingLevelId ? updated : l));
      } else {
        const created = await loyaltyApi.createLevel(payload);
        setLevels([...levels, created]);
      }
      setShowLevelForm(false);
      setEditingLevelId(null);
      setLevelForm({ name: "", min_points: 0, max_points: "", icon: "🥉", color: "orange" });
      flash("Nível salvo!");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erro ao salvar."); }
    finally { setSaving(false); }
  }

  async function deleteLevel(id: string) {
    if (!confirm("Remover este nível?")) return;
    await loyaltyApi.deleteLevel(id);
    setLevels(levels.filter(l => l.id !== id));
    flash("Nível removido.");
  }

  function editLevel(l: ApiLoyaltyLevel) {
    setLevelForm({ name: l.name, min_points: l.min_points, max_points: l.max_points?.toString() ?? "", icon: l.icon, color: l.color });
    setEditingLevelId(l.id);
    setShowLevelForm(true);
  }

  // ── Benefit CRUD ──────────────────────────────────────────────────────────────

  async function saveBenefit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...benefitForm,
        expires_in_days: benefitForm.expires_in_days ? Number(benefitForm.expires_in_days) : null,
      } as Omit<ApiLoyaltyBenefit, "id" | "created_at">;
      if (editingBenefitId) {
        const updated = await loyaltyApi.updateBenefit(editingBenefitId, payload);
        setBenefits(benefits.map(b => b.id === editingBenefitId ? updated : b));
      } else {
        const created = await loyaltyApi.createBenefit(payload);
        setBenefits([...benefits, created]);
      }
      setShowBenefitForm(false);
      setEditingBenefitId(null);
      setBenefitForm({ level_id: "", benefit_type: "discount", label: "", description: "", value: 0, min_order_value: 0, expires_in_days: "", usage_limit: 1, stackable: false, active: true });
      flash("Benefício salvo!");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erro ao salvar."); }
    finally { setSaving(false); }
  }

  async function deleteBenefit(id: string) {
    if (!confirm("Remover benefício?")) return;
    await loyaltyApi.deleteBenefit(id);
    setBenefits(benefits.filter(b => b.id !== id));
    flash("Benefício removido.");
  }

  function editBenefit(b: ApiLoyaltyBenefit) {
    setBenefitForm({ ...b, expires_in_days: b.expires_in_days?.toString() ?? "", description: b.description ?? "" });
    setEditingBenefitId(b.id);
    setShowBenefitForm(true);
  }

  // ── Reward CRUD ───────────────────────────────────────────────────────────────

  async function saveReward(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const created = await loyaltyApi.createReward(rewardForm);
      setRewards([...rewards, created]);
      setShowRewardForm(false);
      setRewardForm({ label: "", points_required: 100, icon: "🎁", active: true });
      flash("Recompensa criada!");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erro."); }
    finally { setSaving(false); }
  }

  // ── Point adjustment ──────────────────────────────────────────────────────────

  async function adjustPoints(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await loyaltyApi.adminAdjustPoints(pointsForm.customer_id, pointsForm.points, pointsForm.description);
      flash(`${pointsForm.points > 0 ? "+" : ""}${pointsForm.points} pontos aplicados.`);
      setPointsForm({ customer_id: "", points: 0, description: "Ajuste manual" });
      loadCustomers();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Erro."); }
    finally { setSaving(false); }
  }

  async function closeCycle(customer_id: string) {
    if (!confirm("Encerrar ciclo agora e aplicar rollover?")) return;
    await loyaltyApi.adminCloseCycle(customer_id);
    flash("Ciclo encerrado e rollover aplicado.");
    loadCustomers();
  }

  const levelName = (id: string | null) => levels.find(l => l.id === id)?.name ?? "—";

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex items-center gap-3 flex-shrink-0">
            <Trophy size={22} className="text-gold" />
            <div>
              <h2 className="text-xl font-bold text-cream">Fidelidade — Retention Engine Pro</h2>
              <p className="text-stone text-xs">Níveis, benefícios, ciclos mensais e clientes</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-surface-02 border-b border-surface-03 px-8 flex gap-1 flex-shrink-0">
            {([
              ["levels",    "Níveis",      Star],
              ["benefits",  "Benefícios",  Gift],
              ["customers", "Clientes",    Users],
              ["points",    "Pontos",      Coins],
            ] as [Tab, string, React.ElementType][]).map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === key
                    ? "border-gold text-gold"
                    : "border-transparent text-stone hover:text-parchment"
                }`}
              >
                <Icon size={15} /> {label}
              </button>
            ))}
          </div>

          {/* Alerts */}
          {error && (
            <div className="mx-8 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex justify-between">
              {error}
              <button onClick={() => setError("")}><X size={14} /></button>
            </div>
          )}
          {success && (
            <div className="mx-8 mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
              {success}
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex justify-center items-center h-40 text-stone text-sm">Carregando...</div>
            ) : (
              <>
                {/* ── Levels Tab ─────────────────────────────────────────── */}
                {tab === "levels" && (
                  <div className="max-w-4xl space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-cream font-semibold">Níveis de Fidelidade</h3>
                      <button
                        onClick={() => { setShowLevelForm(true); setEditingLevelId(null); setLevelForm({ name: "", min_points: 0, max_points: "", icon: "🥉", color: "orange" }); }}
                        className="flex items-center gap-2 px-4 py-2 bg-gold text-cream rounded-lg text-sm font-medium hover:bg-gold/90"
                      >
                        <Plus size={15} /> Novo Nível
                      </button>
                    </div>

                    {showLevelForm && (
                      <form onSubmit={saveLevel} className="bg-surface-02 rounded-xl border border-surface-03 p-5 space-y-4">
                        <h4 className="text-cream font-semibold text-sm">{editingLevelId ? "Editar Nível" : "Novo Nível"}</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="text-stone text-xs mb-1 block">Nome</label>
                            <input value={levelForm.name} onChange={e => setLevelForm(f => ({ ...f, name: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" required />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Ícone</label>
                            <input value={levelForm.icon} onChange={e => setLevelForm(f => ({ ...f, icon: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Pontos mínimos</label>
                            <input type="number" value={levelForm.min_points} onChange={e => setLevelForm(f => ({ ...f, min_points: Number(e.target.value) }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Pontos máximos (vazio = topo)</label>
                            <input type="number" value={levelForm.max_points} onChange={e => setLevelForm(f => ({ ...f, max_points: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Cor</label>
                            <select value={levelForm.color} onChange={e => setLevelForm(f => ({ ...f, color: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none">
                              {Object.entries(colorPalette).map(([k, v]) => (
                                <option key={k} value={k}>{v.label}</option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button type="submit" disabled={saving} className="flex items-center gap-2 px-4 py-2 bg-gold text-cream rounded-lg text-sm disabled:opacity-40">
                            <Save size={14} /> {saving ? "Salvando..." : "Salvar"}
                          </button>
                          <button type="button" onClick={() => setShowLevelForm(false)} className="px-4 py-2 bg-surface-03 text-parchment rounded-lg text-sm">
                            Cancelar
                          </button>
                        </div>
                      </form>
                    )}

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {levels.map(level => {
                        const cp = colorPalette[level.color] ?? colorPalette.orange;
                        const levelBenefits = benefits.filter(b => b.level_id === level.id);
                        return (
                          <div key={level.id} className="bg-surface-02 rounded-xl border border-surface-03 p-5">
                            <div className="flex items-center gap-3 mb-3">
                              <span className="text-2xl">{level.icon}</span>
                              <div className="flex-1">
                                <p className={`font-bold ${cp.text}`}>{level.name}</p>
                                <p className="text-stone text-xs">{level.min_points} — {level.max_points ?? "∞"} pts</p>
                              </div>
                              <div className="flex gap-1">
                                <button onClick={() => editLevel(level)} className="p-2 text-stone hover:text-gold rounded-lg hover:bg-surface-03">
                                  <Edit2 size={14} />
                                </button>
                                <button onClick={() => deleteLevel(level.id)} className="p-2 text-stone hover:text-red-400 rounded-lg hover:bg-surface-03">
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                            <p className="text-stone text-xs">{levelBenefits.length} benefício(s) configurado(s)</p>
                          </div>
                        );
                      })}
                    </div>

                    {/* Rewards sub-section */}
                    <div className="mt-6">
                      <div className="flex justify-between items-center mb-3">
                        <h3 className="text-cream font-semibold text-sm">Recompensas por Pontos</h3>
                        <button onClick={() => setShowRewardForm(v => !v)} className="flex items-center gap-1 px-3 py-1.5 bg-surface-03 text-parchment rounded-lg text-xs hover:bg-surface-03/80">
                          <Plus size={12} /> Nova
                        </button>
                      </div>

                      {showRewardForm && (
                        <form onSubmit={saveReward} className="bg-surface-02 rounded-xl border border-surface-03 p-4 mb-4 grid grid-cols-3 gap-3">
                          <div>
                            <label className="text-stone text-xs mb-1 block">Label</label>
                            <input value={rewardForm.label} onChange={e => setRewardForm(f => ({ ...f, label: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" required />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Pontos necessários</label>
                            <input type="number" value={rewardForm.points_required} onChange={e => setRewardForm(f => ({ ...f, points_required: Number(e.target.value) }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Ícone</label>
                            <input value={rewardForm.icon} onChange={e => setRewardForm(f => ({ ...f, icon: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div className="col-span-3 flex gap-2">
                            <button type="submit" disabled={saving} className="px-4 py-2 bg-gold text-cream rounded-lg text-sm disabled:opacity-40"><Save size={13} /></button>
                            <button type="button" onClick={() => setShowRewardForm(false)} className="px-4 py-2 bg-surface-03 text-parchment rounded-lg text-sm"><X size={13} /></button>
                          </div>
                        </form>
                      )}

                      <div className="space-y-2">
                        {rewards.map(r => (
                          <div key={r.id} className="flex items-center gap-3 bg-surface-02 rounded-lg px-4 py-3 border border-surface-03">
                            <span className="text-xl">{r.icon}</span>
                            <div className="flex-1">
                              <p className="text-cream text-sm">{r.label}</p>
                              <p className="text-stone text-xs">{r.points_required} pontos</p>
                            </div>
                            <button onClick={async () => { if (!confirm("Remover?")) return; await loyaltyApi.deleteReward(r.id); setRewards(rewards.filter(x => x.id !== r.id)); }} className="p-1.5 text-stone hover:text-red-400">
                              <Trash2 size={13} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* ── Benefits Tab ───────────────────────────────────────── */}
                {tab === "benefits" && (
                  <div className="max-w-5xl space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-cream font-semibold">Benefícios por Nível</h3>
                      <button
                        onClick={() => { setShowBenefitForm(true); setEditingBenefitId(null); setBenefitForm({ level_id: levels[0]?.id ?? "", benefit_type: "discount", label: "", description: "", value: 0, min_order_value: 0, expires_in_days: "", usage_limit: 1, stackable: false, active: true }); }}
                        className="flex items-center gap-2 px-4 py-2 bg-gold text-cream rounded-lg text-sm font-medium hover:bg-gold/90"
                      >
                        <Plus size={15} /> Novo Benefício
                      </button>
                    </div>

                    {showBenefitForm && (
                      <form onSubmit={saveBenefit} className="bg-surface-02 rounded-xl border border-surface-03 p-5 space-y-4">
                        <h4 className="text-cream font-semibold text-sm">{editingBenefitId ? "Editar Benefício" : "Novo Benefício"}</h4>
                        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                          <div>
                            <label className="text-stone text-xs mb-1 block">Nível</label>
                            <select value={benefitForm.level_id} onChange={e => setBenefitForm(f => ({ ...f, level_id: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" required>
                              {levels.map(l => <option key={l.id} value={l.id}>{l.icon} {l.name}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Tipo</label>
                            <select value={benefitForm.benefit_type} onChange={e => setBenefitForm(f => ({ ...f, benefit_type: e.target.value as ApiLoyaltyBenefit["benefit_type"] }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none">
                              {Object.entries(BENEFIT_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Label</label>
                            <input value={benefitForm.label} onChange={e => setBenefitForm(f => ({ ...f, label: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" required />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Valor (R$ ou %)</label>
                            <input type="number" step="0.01" value={benefitForm.value} onChange={e => setBenefitForm(f => ({ ...f, value: Number(e.target.value) }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Pedido mínimo (R$)</label>
                            <input type="number" step="0.01" value={benefitForm.min_order_value} onChange={e => setBenefitForm(f => ({ ...f, min_order_value: Number(e.target.value) }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div>
                            <label className="text-stone text-xs mb-1 block">Limite de uso / ciclo</label>
                            <input type="number" value={benefitForm.usage_limit} onChange={e => setBenefitForm(f => ({ ...f, usage_limit: Number(e.target.value) }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div className="col-span-2 lg:col-span-3">
                            <label className="text-stone text-xs mb-1 block">Descrição</label>
                            <input value={benefitForm.description} onChange={e => setBenefitForm(f => ({ ...f, description: e.target.value }))}
                              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                          </div>
                          <div className="flex items-center gap-3">
                            <label className="flex items-center gap-2 text-parchment text-sm cursor-pointer">
                              <input type="checkbox" checked={benefitForm.stackable} onChange={e => setBenefitForm(f => ({ ...f, stackable: e.target.checked }))} className="accent-gold" />
                              Acumulável
                            </label>
                            <label className="flex items-center gap-2 text-parchment text-sm cursor-pointer">
                              <input type="checkbox" checked={benefitForm.active} onChange={e => setBenefitForm(f => ({ ...f, active: e.target.checked }))} className="accent-gold" />
                              Ativo
                            </label>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button type="submit" disabled={saving} className="flex items-center gap-2 px-4 py-2 bg-gold text-cream rounded-lg text-sm disabled:opacity-40">
                            <Save size={14} /> {saving ? "Salvando..." : "Salvar"}
                          </button>
                          <button type="button" onClick={() => setShowBenefitForm(false)} className="px-4 py-2 bg-surface-03 text-parchment rounded-lg text-sm">Cancelar</button>
                        </div>
                      </form>
                    )}

                    {levels.map(level => {
                      const cp = colorPalette[level.color] ?? colorPalette.orange;
                      const levelBenefits = benefits.filter(b => b.level_id === level.id);
                      return (
                        <div key={level.id} className="bg-surface-02 rounded-xl border border-surface-03 p-5">
                          <div className="flex items-center gap-3 mb-4">
                            <span className="text-2xl">{level.icon}</span>
                            <p className={`font-bold ${cp.text}`}>{level.name}</p>
                            <span className="text-stone text-xs ml-auto">{level.min_points}+ pts</span>
                          </div>
                          {levelBenefits.length === 0 ? (
                            <p className="text-stone text-xs">Nenhum benefício configurado.</p>
                          ) : (
                            <div className="space-y-2">
                              {levelBenefits.map(b => (
                                <div key={b.id} className="flex items-center gap-3 bg-surface-03/50 rounded-lg px-4 py-2.5">
                                  <div className="flex-1 min-w-0">
                                    <p className="text-cream text-sm font-medium">{b.label}</p>
                                    <p className="text-stone text-xs">{BENEFIT_TYPE_LABELS[b.benefit_type]} · uso {b.usage_limit}x/ciclo{b.min_order_value > 0 ? ` · min R$${b.min_order_value}` : ""}</p>
                                  </div>
                                  <span className={`text-xs px-2 py-0.5 rounded-full ${b.active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                                    {b.active ? "Ativo" : "Inativo"}
                                  </span>
                                  <button onClick={() => editBenefit(b)} className="p-1.5 text-stone hover:text-gold"><Edit2 size={13} /></button>
                                  <button onClick={() => deleteBenefit(b.id)} className="p-1.5 text-stone hover:text-red-400"><Trash2 size={13} /></button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* ── Customers Tab ──────────────────────────────────────── */}
                {tab === "customers" && (
                  <div className="max-w-5xl space-y-4">
                    <div className="flex items-center gap-4">
                      <h3 className="text-cream font-semibold">Clientes por Nível</h3>
                      <select value={filterLevel} onChange={e => setFilterLevel(e.target.value)}
                        className="bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none">
                        <option value="">Todos os níveis</option>
                        {levels.map(l => <option key={l.id} value={l.id}>{l.icon} {l.name}</option>)}
                      </select>
                      <button onClick={loadCustomers} className="p-2 text-stone hover:text-gold"><RefreshCw size={15} /></button>
                      <span className="text-stone text-xs ml-auto">{customers.length} clientes</span>
                    </div>

                    <div className="space-y-2">
                      {customers.map(c => {
                        const isExpanded = expandedCustomer === c.customer_id;
                        const cp = c.level ? colorPalette[c.level.color] ?? colorPalette.orange : null;
                        return (
                          <div key={c.id} className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                            <button
                              onClick={() => setExpandedCustomer(isExpanded ? null : c.customer_id)}
                              className="w-full flex items-center gap-4 px-5 py-4 hover:bg-surface-03/30 transition-colors text-left"
                            >
                              <span className="text-xl">{c.level?.icon ?? "—"}</span>
                              <div className="flex-1 min-w-0">
                                <p className="text-cream text-sm font-medium">{c.customer_id}</p>
                                <p className="text-stone text-xs">{levelName(c.level?.id ?? null)}</p>
                              </div>
                              <div className="text-right mr-4">
                                <p className={`font-bold text-sm ${cp?.text ?? "text-stone"}`}>{c.total_points} pts</p>
                                <p className="text-stone text-xs">lifetime: {c.lifetime_points}</p>
                              </div>
                              {isExpanded ? <ChevronUp size={16} className="text-stone" /> : <ChevronDown size={16} className="text-stone" />}
                            </button>

                            {isExpanded && (
                              <div className="px-5 pb-4 border-t border-surface-03 pt-4 space-y-3">
                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                                  <Stat label="Rollover" value={`${c.rollover_points} pts`} />
                                  <Stat label="Ciclo início" value={c.cycle_start_date ? new Date(c.cycle_start_date).toLocaleDateString("pt-BR") : "—"} />
                                  <Stat label="Ciclo fim" value={c.cycle_end_date ? new Date(c.cycle_end_date).toLocaleDateString("pt-BR") : "—"} />
                                  <Stat label="Última atividade" value={c.last_activity_at ? new Date(c.last_activity_at).toLocaleDateString("pt-BR") : "—"} />
                                </div>
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => { setPointsForm(f => ({ ...f, customer_id: c.customer_id })); setTab("points"); }}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-gold/10 text-gold border border-gold/30 rounded-lg text-xs hover:bg-gold/20"
                                  >
                                    <ArrowUpDown size={12} /> Ajustar pontos
                                  </button>
                                  <button
                                    onClick={() => closeCycle(c.customer_id)}
                                    className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-03 text-parchment rounded-lg text-xs hover:bg-surface-03/80"
                                  >
                                    <Layers size={12} /> Encerrar ciclo
                                  </button>
                                </div>

                                {c.transactions && c.transactions.length > 0 && (
                                  <div>
                                    <p className="text-stone text-xs mb-2">Últimas transações</p>
                                    <div className="space-y-1 max-h-40 overflow-y-auto">
                                      {c.transactions.slice(0, 10).map(tx => (
                                        <div key={tx.id} className="flex items-center gap-2 text-xs">
                                          <span className={tx.points > 0 ? "text-green-400" : "text-red-400"}>
                                            {tx.points > 0 ? "+" : ""}{tx.points}
                                          </span>
                                          <span className="text-stone flex-1">{tx.description ?? tx.transaction_type}</span>
                                          <span className="text-stone/60">{new Date(tx.created_at).toLocaleDateString("pt-BR")}</span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                      {customers.length === 0 && (
                        <div className="text-center text-stone text-sm py-12">Nenhum cliente encontrado.</div>
                      )}
                    </div>
                  </div>
                )}

                {/* ── Points Tab ─────────────────────────────────────────── */}
                {tab === "points" && (
                  <div className="max-w-xl space-y-4">
                    <h3 className="text-cream font-semibold">Ajuste Manual de Pontos</h3>
                    <div className="bg-surface-02 rounded-xl border border-surface-03 p-6">
                      <form onSubmit={adjustPoints} className="space-y-4">
                        <div>
                          <label className="text-stone text-xs mb-1 block">ID do Cliente</label>
                          <input value={pointsForm.customer_id} onChange={e => setPointsForm(f => ({ ...f, customer_id: e.target.value }))}
                            placeholder="customer_id..."
                            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" required />
                        </div>
                        <div>
                          <label className="text-stone text-xs mb-1 block">Pontos (positivo = adicionar, negativo = remover)</label>
                          <input type="number" value={pointsForm.points} onChange={e => setPointsForm(f => ({ ...f, points: Number(e.target.value) }))}
                            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" required />
                        </div>
                        <div>
                          <label className="text-stone text-xs mb-1 block">Motivo</label>
                          <input value={pointsForm.description} onChange={e => setPointsForm(f => ({ ...f, description: e.target.value }))}
                            className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                        </div>
                        <button type="submit" disabled={saving} className="flex items-center gap-2 px-5 py-2 bg-gold text-cream rounded-lg text-sm font-semibold disabled:opacity-40">
                          <Save size={14} /> {saving ? "Aplicando..." : "Aplicar"}
                        </button>
                      </form>
                    </div>

                    <div className="bg-surface-02 rounded-xl border border-surface-03 p-5">
                      <h4 className="text-cream font-semibold text-sm mb-3">Encerrar Ciclo Manualmente</h4>
                      <p className="text-stone text-xs mb-3">50% dos pontos restantes são rolados para o próximo ciclo. O restante expira.</p>
                      <div className="flex gap-3">
                        <input value={pointsForm.customer_id} onChange={e => setPointsForm(f => ({ ...f, customer_id: e.target.value }))}
                          placeholder="customer_id..."
                          className="flex-1 bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:border-gold outline-none" />
                        <button
                          onClick={() => pointsForm.customer_id && closeCycle(pointsForm.customer_id)}
                          className="flex items-center gap-1.5 px-4 py-2 bg-surface-03 text-parchment rounded-lg text-sm hover:bg-surface-03/80"
                        >
                          <Layers size={14} /> Encerrar
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-03/50 rounded-lg px-3 py-2">
      <p className="text-stone text-xs">{label}</p>
      <p className="text-cream text-sm font-medium">{value}</p>
    </div>
  );
}
