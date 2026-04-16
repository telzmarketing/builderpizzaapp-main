import { useState } from "react";
import { Plus, Trash2, Edit2 } from "lucide-react";
import { useApp, Promotion } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";

export default function AdminPromotions() {
  const { promotions, addPromotion, updatePromotion, deletePromotion } = useApp();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Promotion>>({ title: "", subtitle: "", icon: "🍕", active: true });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title || !formData.subtitle) {
      alert("Preencha todos os campos obrigatórios");
      return;
    }
    try {
      if (editingId) {
        await updatePromotion(editingId, formData);
        setEditingId(null);
      } else {
        await addPromotion({ title: formData.title!, subtitle: formData.subtitle!, icon: formData.icon || "🍕", active: formData.active || false });
      }
      setFormData({ title: "", subtitle: "", icon: "🍕", active: true });
      setShowForm(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar promoção.");
    }
  };

  const handleEdit = (promotion: Promotion) => {
    setFormData(promotion);
    setEditingId(promotion.id);
    setShowForm(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-slate-800 px-8 py-4 border-b border-slate-700 flex justify-between items-center sticky top-0 z-20">
            <h2 className="text-2xl font-bold text-white">Gerenciar Promoções</h2>
            <button
              onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ title: "", subtitle: "", icon: "🍕", active: true }); }}
              className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded-lg transition-colors"
            >
              <Plus size={20} />
              Nova Promoção
            </button>
          </div>

          <div className="p-8">
            {showForm && (
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-8">
                <h3 className="text-xl font-bold text-white mb-4">{editingId ? "Editar Promoção" : "Nova Promoção"}</h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-300 text-sm font-medium mb-2">Título *</label>
                      <input
                        type="text"
                        value={formData.title || ""}
                        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500"
                        placeholder="Ex: 20% off em"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-300 text-sm font-medium mb-2">Subtítulo *</label>
                      <input
                        type="text"
                        value={formData.subtitle || ""}
                        onChange={(e) => setFormData({ ...formData, subtitle: e.target.value })}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500"
                        placeholder="Ex: qualquer fast food"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-300 text-sm font-medium mb-2">Ícone / Emoji</label>
                    <input
                      type="text"
                      value={formData.icon || ""}
                      onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500 text-2xl"
                      placeholder="🍕"
                    />
                    <p className="text-slate-500 text-xs mt-1">Cole um emoji ou URL de imagem</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={formData.active || false}
                      onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                      className="w-4 h-4 rounded accent-orange-500"
                      id="active-check"
                    />
                    <label htmlFor="active-check" className="text-slate-300 text-sm font-medium cursor-pointer">Ativa (visível na home)</label>
                  </div>
                  <div className="flex gap-3 pt-4">
                    <button type="submit" className="flex-1 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                      {editingId ? "Salvar Alterações" : "Criar Promoção"}
                    </button>
                    <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="flex-1 bg-slate-700 hover:bg-slate-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                      Cancelar
                    </button>
                  </div>
                </form>
              </div>
            )}

            <div className="space-y-4">
              {promotions.map((promotion) => (
                <div key={promotion.id} className="bg-slate-800 rounded-xl p-6 border border-slate-700 flex items-center justify-between">
                  <div className="flex items-center gap-6 flex-1">
                    <div className="text-5xl">{promotion.icon}</div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-white">{promotion.title}</h3>
                      <p className="text-slate-400 text-sm">{promotion.subtitle}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={promotion.active}
                        onChange={() => updatePromotion(promotion.id, { active: !promotion.active })}
                        className="w-5 h-5 rounded accent-orange-500 cursor-pointer"
                      />
                      <span className={`text-sm font-medium ${promotion.active ? "text-green-400" : "text-slate-400"}`}>
                        {promotion.active ? "Ativa" : "Inativa"}
                      </span>
                    </div>
                    <button onClick={() => handleEdit(promotion)} className="p-3 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors">
                      <Edit2 size={18} />
                    </button>
                    <button onClick={() => deletePromotion(promotion.id)} className="p-3 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors">
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {promotions.length === 0 && (
              <div className="text-center py-12">
                <p className="text-slate-400 text-lg">Nenhuma promoção cadastrada</p>
                <button onClick={() => setShowForm(true)} className="mt-4 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-6 rounded-lg transition-colors inline-flex items-center gap-2">
                  <Plus size={20} />
                  Criar Primeira Promoção
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
