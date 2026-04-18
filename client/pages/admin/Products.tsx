import { useState } from "react";
import { Plus, Trash2, Edit2, Settings2 } from "lucide-react";
import { useApp, Pizza, PricingRule } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";
import ImageUpload from "@/components/admin/ImageUpload";

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

  const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold text-sm";

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex justify-between items-center sticky top-0 z-20">
            <h2 className="text-2xl font-bold text-cream">Gerenciar Produtos</h2>
            <button
              onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: "🍕", rating: 4.5 }); }}
              className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
            >
              <Plus size={20} />
              Novo Produto
            </button>
          </div>

          <div className="p-8">
            {showForm && (
              <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 mb-8">
                <h3 className="text-xl font-bold text-cream mb-4">{editingId ? "Editar Produto" : "Novo Produto"}</h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Nome do Produto *</label>
                      <input type="text" value={formData.name || ""} onChange={(e) => setFormData({ ...formData, name: e.target.value })} className={cls} placeholder="Ex: Pizza Pepperoni" />
                    </div>
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Preço (R$) *</label>
                      <input type="number" value={formData.price || ""} onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) })} className={cls} placeholder="12.99" step="0.01" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-parchment text-sm font-medium mb-2">Descrição *</label>
                    <textarea value={formData.description || ""} onChange={(e) => setFormData({ ...formData, description: e.target.value })} className={`${cls} resize-none`} placeholder="Descreva o produto..." rows={3} />
                  </div>
                  <div className="grid grid-cols-2 gap-4 items-start">
                    <ImageUpload
                      value={formData.icon || ""}
                      onChange={(v) => setFormData({ ...formData, icon: v })}
                      label="Ícone / Imagem do produto"
                      sizeGuide="Tamanho recomendado: 200×200px, máx. 200KB"
                      hint="Faça upload de uma imagem ou use um emoji 🍕"
                      maxKB={200}
                    />
                    <div>
                      <label className="block text-parchment text-sm font-medium mb-2">Avaliação (1–5)</label>
                      <input type="number" value={formData.rating || ""} onChange={(e) => setFormData({ ...formData, rating: parseFloat(e.target.value) })} className={cls} placeholder="4.5" min="1" max="5" step="0.1" />
                    </div>
                  </div>
                  <div className="flex gap-3 pt-4">
                    <button type="submit" className="flex-1 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors">
                      {editingId ? "Salvar Alterações" : "Adicionar Produto"}
                    </button>
                    <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} className="flex-1 bg-surface-03 hover:bg-brand-mid text-cream font-bold py-2 px-4 rounded-lg transition-colors">
                      Cancelar
                    </button>
                  </div>
                </form>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {products.map((product) => (
                <div key={product.id} className="bg-surface-02 rounded-xl p-6 border border-surface-03">
                  <div className="w-16 h-16 rounded-xl bg-surface-03 flex items-center justify-center mb-4 overflow-hidden">
                    {product.icon?.startsWith("data:") || product.icon?.startsWith("http") ? (
                      <img src={product.icon} alt={product.name} className="w-full h-full object-contain" />
                    ) : (
                      <span className="text-4xl">{product.icon || "🍕"}</span>
                    )}
                  </div>
                  <h3 className="text-lg font-bold text-cream mb-2">{product.name}</h3>
                  <p className="text-stone text-sm mb-3 line-clamp-2">{product.description}</p>
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-gold font-bold">R$ {product.price.toFixed(2)}</span>
                    <span className="text-stone text-sm">⭐ {product.rating}</span>
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
                <p className="text-stone text-lg">Nenhum produto cadastrado</p>
                <button onClick={() => setShowForm(true)} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg transition-colors inline-flex items-center gap-2">
                  <Plus size={20} />
                  Criar Primeiro Produto
                </button>
              </div>
            )}

            {/* ── Multi-Flavor Config ── */}
            <div className="mt-10 bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
              <div className="px-6 py-4 border-b border-surface-03 flex items-center gap-3">
                <Settings2 size={20} className="text-gold" />
                <div>
                  <h3 className="text-lg font-bold text-cream">Configuração de Multi-Sabor</h3>
                  <p className="text-stone text-sm">Define como funcionam as pizzas com divisão de sabores</p>
                </div>
              </div>
              <div className="p-6 space-y-6">
                <div>
                  <label className="block text-parchment text-sm font-bold mb-3">Máximo de sabores por pizza</label>
                  <div className="flex gap-3">
                    {([2, 3] as (2 | 3)[]).map((n) => (
                      <button
                        key={n}
                        onClick={() => { updateMultiFlavorsConfig({ maxFlavors: n }); handleConfigSave(); }}
                        className={`flex-1 py-3 rounded-xl border text-sm font-bold transition-all ${
                          multiFlavorsConfig.maxFlavors === n
                            ? "bg-gold text-cream border-gold shadow-lg shadow-gold/30"
                            : "bg-surface-03 text-parchment border-surface-03 hover:border-gold/50"
                        }`}
                      >
                        {n} Sabores
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-parchment text-sm font-bold mb-3">Regra de preço para multi-sabores</label>
                  <div className="space-y-2">
                    {PRICING_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => { updateMultiFlavorsConfig({ pricingRule: opt.value }); handleConfigSave(); }}
                        className={`w-full text-left px-4 py-3 rounded-xl border transition-all ${
                          multiFlavorsConfig.pricingRule === opt.value
                            ? "bg-gold/20 border-gold text-cream"
                            : "bg-surface-03 border-surface-03 text-parchment hover:border-gold/50"
                        }`}
                      >
                        <p className="font-semibold text-sm">{opt.label}</p>
                        <p className="text-stone text-xs mt-0.5">{opt.description}</p>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex justify-end">
                  <button onClick={handleConfigSave} className={`px-6 py-2 rounded-lg font-bold text-sm transition-colors ${configSaved ? "bg-green-500 text-white" : "bg-gold hover:bg-gold/90 text-cream"}`}>
                    {configSaved ? "Salvo!" : "Salvar configuração"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
