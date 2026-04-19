import { useState } from "react";
import { Plus, Trash2, Edit2, Settings2, Tag } from "lucide-react";
import { useApp, Pizza, PricingRule } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";
import ImageUpload from "@/components/admin/ImageUpload";

const PRICING_OPTIONS: { value: PricingRule; label: string; description: string }[] = [
  { value: "most_expensive", label: "Mais Caro", description: "Cliente paga pelo sabor mais caro (padrão iFood)" },
  { value: "average", label: "Média", description: "Preço é a média aritmética dos sabores" },
  { value: "proportional", label: "Proporcional", description: "Cada parte paga sua fração do sabor" },
];

type PTab = "produtos" | "categorias" | "config";

export default function AdminProducts() {
  const { products, addProduct, updateProduct, deleteProduct, multiFlavorsConfig, updateMultiFlavorsConfig, siteContent, updateSiteContent } = useApp();
  const [activeTab, setActiveTab] = useState<PTab>("produtos");
  const [configSaved, setConfigSaved] = useState(false);

  // ── Categories ──────────────────────────────────────────────────────────────
  const categories = siteContent.home.categories;
  const [newCategory, setNewCategory] = useState("");

  const addCategory = () => {
    const t = newCategory.trim();
    if (!t || categories.includes(t)) return;
    updateSiteContent({ home: { ...siteContent.home, categories: [...categories, t] } } as any);
    setNewCategory("");
  };

  const removeCategory = (cat: string) => {
    updateSiteContent({ home: { ...siteContent.home, categories: categories.filter((c) => c !== cat) } } as any);
  };

  // ── Products CRUD ───────────────────────────────────────────────────────────
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Pizza>>({ name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5 });

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
        await addProduct({
          name: formData.name!, description: formData.description!,
          price: formData.price!, icon: formData.icon || "🍕",
          category: formData.category || null,
          rating: formData.rating || 4.5, active: true,
        } as any);
      }
      setFormData({ name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5 });
      setShowForm(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar produto.");
    }
  };

  const handleEdit = (product: Pizza) => {
    setFormData({ ...product, category: (product as any).category ?? "" });
    setEditingId(product.id);
    setShowForm(true);
  };

  const handleConfigSave = async () => {
    try {
      await updateMultiFlavorsConfig(multiFlavorsConfig);
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 2000);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar configuração.");
    }
  };

  const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 text-cream placeholder-stone focus:outline-none focus:border-gold text-sm";

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />
        <div className="flex-1 overflow-auto">

          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex justify-between items-center sticky top-0 z-20">
            <div>
              <h2 className="text-2xl font-bold text-cream">Produtos</h2>
              <p className="text-stone text-sm">{products.length} produtos · {categories.length} categorias</p>
            </div>
            {activeTab === "produtos" && (
              <button
                onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ name: "", description: "", price: 0, icon: "🍕", category: "", rating: 4.5 }); }}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors"
              >
                <Plus size={20} />
                Novo Produto
              </button>
            )}
          </div>

          {/* Tabs */}
          <div className="px-8 pt-4 flex gap-2">
            {([
              { key: "produtos", label: "Produtos" },
              { key: "categorias", label: "Categorias" },
              { key: "config", label: "Configurações" },
            ] as { key: PTab; label: string }[]).map(({ key, label }) => (
              <button key={key} onClick={() => setActiveTab(key)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${activeTab === key ? "bg-gold text-cream" : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"}`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="p-8">

            {/* ── TAB: PRODUTOS ── */}
            {activeTab === "produtos" && (
              <>
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
                      <div>
                        <label className="block text-parchment text-sm font-medium mb-2">Categoria</label>
                        <select
                          value={(formData as any).category || ""}
                          onChange={(e) => setFormData({ ...formData, category: e.target.value } as any)}
                          className={cls}
                        >
                          <option value="">Sem categoria</option>
                          {categories.slice(1).map((cat) => (
                            <option key={cat} value={cat}>{cat}</option>
                          ))}
                        </select>
                      </div>
                      <div className="grid grid-cols-2 gap-4 items-start">
                        <ImageUpload
                          value={formData.icon || ""}
                          onChange={(v) => setFormData({ ...formData, icon: v })}
                          label="Ícone / Imagem do produto"
                          sizeGuide="Tamanho recomendado: 200×200px, máx. 512KB"
                          hint="Faça upload de uma imagem ou use um emoji 🍕"
                          maxKB={512}
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
                      <h3 className="text-lg font-bold text-cream mb-1">{product.name}</h3>
                      {(product as any).category && (
                        <span className="inline-flex items-center gap-1 text-xs bg-gold/20 text-gold border border-gold/30 px-2 py-0.5 rounded-full mb-2">
                          <Tag size={10} />
                          {(product as any).category}
                        </span>
                      )}
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
                        <button onClick={() => deleteProduct(product.id)} className="flex items-center justify-center gap-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 font-medium py-2 px-3 rounded-lg transition-colors">
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {products.length === 0 && (
                  <div className="text-center py-12">
                    <p className="text-stone text-lg">Nenhum produto cadastrado</p>
                    <button onClick={() => setShowForm(true)} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg transition-colors inline-flex items-center gap-2">
                      <Plus size={20} /> Adicionar Primeiro Produto
                    </button>
                  </div>
                )}
              </>
            )}

            {/* ── TAB: CATEGORIAS ── */}
            {activeTab === "categorias" && (
              <div className="max-w-xl">
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 space-y-4">
                  <div className="flex items-center gap-3 pb-3 border-b border-surface-03">
                    <Tag size={18} className="text-gold" />
                    <div>
                      <h3 className="text-cream font-bold">Categorias do Cardápio</h3>
                      <p className="text-stone text-sm">Filtros exibidos na home. A primeira categoria é o "Ver todos".</p>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 min-h-[2rem]">
                    {categories.map((cat, i) => (
                      <div key={cat} className="flex items-center gap-1.5 bg-surface-03 rounded-full px-3 py-1.5">
                        <span className="text-cream text-sm">{cat}</span>
                        {i === 0 && <span className="text-xs text-stone">(padrão)</span>}
                        {i > 0 && (
                          <button onClick={() => removeCategory(cat)} className="text-stone hover:text-red-400 transition-colors ml-1">
                            <Trash2 size={11} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCategory}
                      onChange={(e) => setNewCategory(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && addCategory()}
                      className={cls}
                      placeholder="Nova categoria (ex: Pizzas, Bebidas...)"
                    />
                    <button onClick={addCategory} className="flex items-center gap-1.5 px-4 py-2 bg-gold hover:bg-gold/90 text-cream rounded-lg transition-colors text-sm font-medium flex-shrink-0">
                      <Plus size={15} /> Adicionar
                    </button>
                  </div>

                  <p className="text-stone text-xs mt-2">
                    Após criar categorias, edite cada produto para associá-lo a uma categoria.
                  </p>
                </div>
              </div>
            )}

            {/* ── TAB: CONFIG ── */}
            {activeTab === "config" && (
              <div className="max-w-xl">
                <div className="bg-surface-02 rounded-xl p-6 border border-surface-03 space-y-4">
                  <div className="flex items-center gap-3 pb-3 border-b border-surface-03">
                    <Settings2 size={18} className="text-gold" />
                    <div>
                      <h3 className="text-cream font-bold">Configuração de Multi-Sabores</h3>
                      <p className="text-stone text-sm">Define como pizzas meio-a-meio são precificadas</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-parchment text-sm font-medium mb-2">Máximo de sabores por pizza</label>
                    <div className="flex gap-3">
                      {[2, 3].map((n) => (
                        <button
                          key={n}
                          onClick={() => updateMultiFlavorsConfig({ ...multiFlavorsConfig, maxFlavors: n as 2 | 3 })}
                          className={`flex-1 py-3 rounded-xl border-2 font-bold transition-all ${multiFlavorsConfig.maxFlavors === n ? "border-gold bg-gold/10 text-gold" : "border-surface-03 text-stone hover:border-gold/50"}`}
                        >
                          {n} {n === 2 ? "sabores" : "sabores"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-parchment text-sm font-medium mb-3">Regra de precificação</label>
                    <div className="space-y-2">
                      {PRICING_OPTIONS.map((opt) => (
                        <button
                          key={opt.value}
                          onClick={() => updateMultiFlavorsConfig({ ...multiFlavorsConfig, pricingRule: opt.value })}
                          className={`w-full text-left p-3 rounded-xl border-2 transition-all ${multiFlavorsConfig.pricingRule === opt.value ? "border-gold bg-gold/10" : "border-surface-03 hover:border-gold/50"}`}
                        >
                          <p className={`font-bold text-sm ${multiFlavorsConfig.pricingRule === opt.value ? "text-gold" : "text-cream"}`}>{opt.label}</p>
                          <p className="text-stone text-xs mt-0.5">{opt.description}</p>
                        </button>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleConfigSave}
                    className={`w-full py-3 rounded-xl font-bold text-sm transition-colors ${configSaved ? "bg-green-500 text-white" : "bg-gold hover:bg-gold/90 text-cream"}`}
                  >
                    {configSaved ? "✓ Salvo!" : "Salvar Configurações"}
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
