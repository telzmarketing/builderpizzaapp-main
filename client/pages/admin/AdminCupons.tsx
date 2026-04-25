import { useState } from "react";
import { Plus, Trash2, Edit2, Tag } from "lucide-react";
import { useApp, Coupon } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";

const emptyForm: Partial<Coupon> = { code: "", description: "", discount: "", expiry: "", icon: "🎟️", type: "percentage", used: false };

const typeLabels: Record<Coupon["type"], string> = { percentage: "Percentual (%)", fixed: "Valor Fixo (R$)" };
const typeColor = (type: Coupon["type"]) => {
  if (type === "percentage") return "bg-gold/20 text-orange-400 border-gold/40";
  return "bg-green-500/20 text-green-400 border-green-500/40";
};

export default function AdminCupons() {
  const { coupons, addCoupon, updateCoupon, deleteCoupon } = useApp();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Coupon>>(emptyForm);
  const [filter, setFilter] = useState<"all" | "available" | "used">("all");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.code || !formData.description || !formData.discount || !formData.expiry) {
      alert("Preencha todos os campos obrigatórios");
      return;
    }
    try {
      if (editingId) {
        await updateCoupon(editingId, formData);
        setEditingId(null);
      } else {
        await addCoupon({
          code: formData.code!.toUpperCase(),
          description: formData.description!,
          discount: formData.discount!,
          expiry: formData.expiry!,
          icon: formData.icon || "🎟️",
          type: formData.type || "percentage",
        });
      }
      setFormData(emptyForm);
      setShowForm(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar cupom.");
    }
  };

  const handleEdit = (coupon: Coupon) => {
    setFormData(coupon);
    setEditingId(coupon.id);
    setShowForm(true);
  };

  const filtered = coupons.filter((c) => {
    if (filter === "available") return !c.used;
    if (filter === "used") return c.used;
    return true;
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex justify-between items-center sticky top-0 z-20">
            <div>
              <h2 className="text-2xl font-bold text-cream">Gerenciar Cupons</h2>
              <p className="text-stone text-sm">{coupons.filter((c) => !c.used).length} disponíveis · {coupons.filter((c) => c.used).length} usados</p>
            </div>
            <button
              onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData(emptyForm); }}
              className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
            >
              <Plus size={20} />
              Novo Cupom
            </button>
          </div>

          <div className="p-8">
            {showForm && (
              <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 mb-8">
                <h3 className="text-xl font-bold text-cream mb-4">{editingId ? "Editar Cupom" : "Novo Cupom"}</h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Código do Cupom *</label>
                      <input
                        type="text"
                        value={formData.code || ""}
                        onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold font-mono tracking-widest uppercase"
                        placeholder="EX: PIZZA20"
                      />
                    </div>
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Tipo de Desconto *</label>
                      <select
                        value={formData.type || "percentage"}
                        onChange={(e) => setFormData({ ...formData, type: e.target.value as Coupon["type"] })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream focus:outline-none focus:border-gold"
                      >
                        <option value="percentage">Percentual (%)</option>
                        <option value="fixed">Valor Fixo (R$)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-parchment text-sm font-medium mb-2">Descrição *</label>
                    <input
                      type="text"
                      value={formData.description || ""}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold"
                      placeholder="Ex: 20% de desconto em qualquer pizza"
                    />
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Texto do Desconto *</label>
                      <input
                        type="text"
                        value={formData.discount || ""}
                        onChange={(e) => setFormData({ ...formData, discount: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold"
                        placeholder="Ex: 20% OFF"
                      />
                    </div>
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Validade *</label>
                      <input
                        type="text"
                        value={formData.expiry || ""}
                        onChange={(e) => setFormData({ ...formData, expiry: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold"
                        placeholder="Ex: 30/04/2026"
                      />
                    </div>
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Ícone / Emoji</label>
                      <input
                        type="text"
                        value={formData.icon || ""}
                        onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold text-2xl"
                        placeholder="🎟️"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={formData.used || false}
                      onChange={(e) => setFormData({ ...formData, used: e.target.checked })}
                      className="w-4 h-4 rounded accent-gold"
                      id="used-check"
                    />
                    <label htmlFor="used-check" className="text-parchment text-sm font-medium cursor-pointer">Marcar como já utilizado</label>
                  </div>

                  <div className="flex gap-3 pt-4">
                    <button type="submit" className="flex-1 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors">
                      {editingId ? "Salvar Alterações" : "Criar Cupom"}
                    </button>
                    <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="flex-1 bg-surface-03 hover:bg-slate-600 text-cream font-bold py-2 px-4 rounded-lg transition-colors">
                      Cancelar
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* Filter Tabs */}
            <div className="flex gap-2 mb-6">
              {(["all", "available", "used"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${filter === f ? "bg-gold text-cream" : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"}`}
                >
                  {f === "all" ? "Todos" : f === "available" ? "Disponíveis" : "Usados"}
                </button>
              ))}
            </div>

            {/* Coupons List */}
            <div className="space-y-4">
              {filtered.map((coupon) => (
                <div key={coupon.id} className={`bg-surface-02 rounded-xl border border-surface-03 overflow-hidden ${coupon.used ? "opacity-60" : ""}`}>
                  <div className="flex items-center gap-4 p-4">
                    <div className="w-14 h-14 rounded-full bg-surface-03 flex items-center justify-center text-3xl flex-shrink-0">
                      {coupon.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-cream font-bold">{coupon.description}</p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs border ${typeColor(coupon.type)}`}>
                          {coupon.discount}
                        </span>
                        <span className="text-stone text-xs font-mono tracking-widest">{coupon.code}</span>
                        <span className="text-stone/70 text-xs">Válido até {coupon.expiry}</span>
                        {coupon.used && <span className="text-xs bg-surface-03 text-stone px-2 py-0.5 rounded-full">Usado</span>}
                      </div>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <button
                        onClick={() => updateCoupon(coupon.id, { used: !coupon.used })}
                        className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${coupon.used ? "bg-green-500/20 text-green-400 hover:bg-green-500/30" : "bg-surface-03 text-parchment hover:bg-slate-600"}`}
                      >
                        {coupon.used ? "Reativar" : "Marcar Usado"}
                      </button>
                      <button onClick={() => handleEdit(coupon)} className="p-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors">
                        <Edit2 size={16} />
                      </button>
                      <button onClick={() => deleteCoupon(coupon.id)} className="p-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {filtered.length === 0 && (
              <div className="text-center py-16">
                <Tag size={48} className="text-slate-600 mx-auto mb-4" />
                <p className="text-stone text-lg">Nenhum cupom aqui</p>
                <button onClick={() => setShowForm(true)} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg transition-colors inline-flex items-center gap-2">
                  <Plus size={20} />
                  Criar Primeiro Cupom
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
