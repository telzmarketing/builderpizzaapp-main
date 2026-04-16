import { useState } from "react";
import { Plus, Trash2, Edit2, Settings2 } from "lucide-react";
import { useApp, Pizza, PricingRule } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";

const PRICING_OPTIONS: { value: PricingRule; label: string; description: string }[] = [
  { value: "most_expensive", label: "Mais Caro", description: "Cliente paga pelo sabor mais caro (padrão iFood)" },
  { value: "average", label: "Média", description: "Preço é a média aritmética dos sabores" },
  { value: "proportional", label: "Proporcional", description: "Cada parte paga sua fração do sabor" },
];

export default function AdminProducts() {
  const { products, addProduct, updateProduct, deleteProduct, multiFlavorsConfig, updateMultiFlavorsConfig } = useApp();
  const [configSaved, setConfigSaved] = useState(false);

  const handleConfigSave = async () => {
    try {
      await updateMultiFlavorsConfig(multiFlavorsConfig);
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 2000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar configuração.");
    }
  };
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Pizza>>({ name: "", description: "", price: 0, icon: "🍕", rating: 4.5 });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.description || !formData.price) {
      alert("Preencha todos os campos obrigatórios");
      return;
    }
    try {
      if (editingId) {
        await updateProduct(editingId, formData);
        setEditingId(null);
      } else {
        await addProduct({ name: formData.name!, description: formData.description!, price: formData.price!, icon: formData.icon || "🍕", rating: formData.rating || 4.5, active: true });
      }
      setFormData({ name: "", description: "", price: 0, icon: "🍕", rating: 4.5 });
      setShowForm(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar produto.");
    }
  };

  const handleEdit = (product: Pizza) => {
    setFormData(product);
    setEditingId(product.id);
    setShowForm(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-slate-800 px-8 py-4 border-b border-slate-700 flex justify-between items-center sticky top-0 z-20">
            <h2 className="text-2xl font-bold text-white">Gerenciar Produtos</h2>
            <button
              onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: "🍕", rating: 4.5 }); }}
              className="flex items-center gap-2 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded-lg transition-colors"
            >
              <Plus size={20} />
              Novo Produto
            </button>
          </div>

          <div className="p-8">
            {showForm && (
              <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-8">
                <h3 className="text-xl font-bold text-white mb-4">{editingId ? "Editar Produto" : "Novo Produto"}</h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-300 text-sm font-medium mb-2">Nome do Produto *</label>
                      <input
                        type="text"
                        value={formData.name || ""}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500"
                        placeholder="Ex: Pizza Pepperoni"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-300 text-sm font-medium mb-2">Preço (R$) *</label>
                      <input
                        type="number"
                        value={formData.price || ""}
                        onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) })}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500"
                        placeholder="12.99"
                        step="0.01"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-300 text-sm font-medium mb-2">Descrição *</label>
                    <textarea
                      value={formData.description || ""}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500 resize-none"
                      placeholder="Descreva o produto..."
                      rows={3}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
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
                    <div>
                      <label className="block text-slate-300 text-sm font-medium mb-2">Avaliação (1–5)</label>
                      <input
                        type="number"
                        value={formData.rating || ""}
                        onChange={(e) => setFormData({ ...formData, rating: parseFloat(e.target.value) })}
                        className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500"
                        placeholder="4.5"
                        min="1" max="5" step="0.1"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 pt-4">
                    <button type="submit" className="flex-1 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                      {editingId ? "Salvar Alterações" : "Adicionar Produto"}
                    </button>
                    <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="flex-1 bg-slate-700 hover:bg-slate-600 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                      Cancelar
                    </button>
                  </div>
                </form>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {products.map((product) => (
                <div key={product.id} className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                  <div className="text-5xl mb-4">{product.icon}</div>
                  <h3 className="text-lg font-bold text-white mb-2">{product.name}</h3>
                  <p className="text-slate-400 text-sm mb-3 line-clamp-2">{product.description}</p>
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-orange-500 font-bold">${product.price.toFixed(2)}</span>
                    <span className="text-slate-400 text-sm">⭐ {product.rating}</span>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => handleEdit(product)} className="flex-1 flex items-center justify-center gap-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 font-medium py-2 px-3 rounded-lg transition-colors">
                      <Edit2 size={16} />
                      Editar
                    </button>
                    <button onClick={() => deleteProduct(product.id)} className="flex-1 flex items-center justify-center gap-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium py-2 px-3 rounded-lg transition-colors">
                      <Trash2 size={16} />
                      Excluir
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {products.length === 0 && (
              <div className="text-center py-12">
                <p className="text-slate-400 text-lg">Nenhum produto cadastrado</p>
                <button onClick={() => setShowForm(true)} className="mt-4 bg-orange-500 hover:bg-orange-600 text-white font-bold py-2 px-6 rounded-lg transition-colors inline-flex items-center gap-2">
                  <Plus size={20} />
                  Criar Primeiro Produto
                </button>
              </div>
            )}

            {/* ── Multi-Flavor Config ─────────────────────────────────────── */}
            <div className="mt-10 bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-700 flex items-center gap-3">
                <Settings2 size={20} className="text-orange-500" />
                <div>
                  <h3 className="text-lg font-bold text-white">Configuração de Multi-Sabor</h3>
                  <p className="text-slate-400 text-sm">Define como funcionam as pizzas com divisão de sabores</p>
                </div>
              </div>

              <div className="p-6 space-y-6">
                {/* Max flavors */}
                <div>
                  <label className="block text-slate-300 text-sm font-bold mb-3">Máximo de sabores por pizza</label>
                  <div className="flex gap-3">
                    {([2, 3] as (2 | 3)[]).map((n) => (
                      <button
                        key={n}
                        onClick={() => { updateMultiFlavorsConfig({ maxFlavors: n }); handleConfigSave(); }}
                        className={`flex-1 py-3 rounded-xl border text-sm font-bold transition-all ${
                          multiFlavorsConfig.maxFlavors === n
                            ? "bg-orange-500 text-white border-orange-500"
                            : "bg-slate-700 text-slate-300 border-slate-600 hover:border-orange-500/50"
                        }`}
                      >
                        {n === 2 ? "🍕½ Até 2 sabores" : "🍕⅓ Até 3 sabores"}
                      </button>
                    ))}
                  </div>
                  <p className="text-slate-500 text-xs mt-2">
                    {multiFlavorsConfig.maxFlavors === 2
                      ? "Clientes poderão escolher: Inteira ou Meio a Meio"
                      : "Clientes poderão escolher: Inteira, Meio a Meio ou 3 Sabores"}
                  </p>
                </div>

                {/* Pricing rule */}
                <div>
                  <label className="block text-slate-300 text-sm font-bold mb-3">Regra de precificação</label>
                  <div className="space-y-2">
                    {PRICING_OPTIONS.map(({ value, label, description }) => (
                      <button
                        key={value}
                        onClick={() => { updateMultiFlavorsConfig({ pricingRule: value }); handleConfigSave(); }}
                        className={`w-full flex items-start gap-4 p-4 rounded-xl border text-left transition-all ${
                          multiFlavorsConfig.pricingRule === value
                            ? "bg-orange-500/10 border-orange-500"
                            : "bg-slate-700/50 border-slate-600 hover:border-orange-500/40"
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full border-2 flex-shrink-0 mt-0.5 flex items-center justify-center ${
                          multiFlavorsConfig.pricingRule === value ? "border-orange-500" : "border-slate-500"
                        }`}>
                          {multiFlavorsConfig.pricingRule === value && (
                            <div className="w-2.5 h-2.5 rounded-full bg-orange-500" />
                          )}
                        </div>
                        <div>
                          <p className={`font-bold text-sm ${multiFlavorsConfig.pricingRule === value ? "text-orange-400" : "text-white"}`}>
                            {label}
                          </p>
                          <p className="text-slate-400 text-xs mt-0.5">{description}</p>
                          {value === "most_expensive" && (
                            <p className="text-slate-500 text-xs mt-1">
                              Ex: Calabresa R$40 + Camarão R$60 → Cliente paga R$60
                            </p>
                          )}
                          {value === "average" && (
                            <p className="text-slate-500 text-xs mt-1">
                              Ex: Calabresa R$40 + Camarão R$60 → Cliente paga R$50
                            </p>
                          )}
                          {value === "proportional" && (
                            <p className="text-slate-500 text-xs mt-1">
                              Ex: Meio a Meio: Calabresa R$40/2 + Camarão R$60/2 → Cliente paga R$50
                            </p>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Preview */}
                <div className="bg-slate-900/60 rounded-xl p-4 border border-slate-700">
                  <p className="text-slate-300 text-sm font-bold mb-2">Configuração atual</p>
                  <div className="flex gap-3 flex-wrap">
                    <span className="text-xs bg-orange-500/20 text-orange-400 border border-orange-500/30 px-3 py-1 rounded-full">
                      Máx. {multiFlavorsConfig.maxFlavors} sabores
                    </span>
                    <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-3 py-1 rounded-full">
                      Preço: {PRICING_OPTIONS.find((o) => o.value === multiFlavorsConfig.pricingRule)?.label}
                    </span>
                    {configSaved && (
                      <span className="text-xs bg-green-500/20 text-green-400 border border-green-500/30 px-3 py-1 rounded-full">
                        ✓ Configuração salva
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
