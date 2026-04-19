import { useState } from "react";
import {
  Save, RefreshCw, Plus, Trash2, ChevronDown, ChevronRight,
  Palette, Home, Navigation, FileText, Image, Activity,
} from "lucide-react";
import { useApp, SiteContent, defaultSiteContent } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";
import ImageUpload from "@/components/admin/ImageUpload";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function Field({
  label, hint, children,
}: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-slate-300 text-sm font-medium mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-slate-500 text-xs mt-1">{hint}</p>}
    </div>
  );
}

function TextInput({
  value, onChange, placeholder, multiline = false,
}: { value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean }) {
  const cls = "w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500 text-sm";
  if (multiline) {
    return (
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={2}
        className={`${cls} resize-none`}
      />
    );
  }
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cls}
    />
  );
}

function Section({
  icon, title, subtitle, children, defaultOpen = false,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-6 py-4 flex items-center gap-4 hover:bg-slate-750 transition-colors text-left"
      >
        <span className="text-orange-500 flex-shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-bold text-base">{title}</h3>
          <p className="text-slate-400 text-sm">{subtitle}</p>
        </div>
        {open ? (
          <ChevronDown size={18} className="text-slate-400 flex-shrink-0" />
        ) : (
          <ChevronRight size={18} className="text-slate-400 flex-shrink-0" />
        )}
      </button>
      {open && <div className="px-6 pb-6 pt-2 border-t border-slate-700 space-y-4">{children}</div>}
    </div>
  );
}

// ─── Tab definition ───────────────────────────────────────────────────────────

type Tab = "marca_midia" | "home" | "nav" | "paginas" | "rastreamento";

const TABS: { id: Tab; icon: React.ReactNode; label: string }[] = [
  { id: "marca_midia", icon: <Palette size={16} />, label: "Marca & Mídia" },
  { id: "home", icon: <Home size={16} />, label: "Home" },
  { id: "nav", icon: <Navigation size={16} />, label: "Navegação" },
  { id: "paginas", icon: <FileText size={16} />, label: "Páginas" },
  { id: "rastreamento", icon: <Activity size={16} />, label: "Rastreamento" },
];

// ─── Main component ───────────────────────────────────────────────────────────

export default function AdminConteudo() {
  const { siteContent, updateSiteContent } = useApp();
  const [draft, setDraft] = useState<SiteContent>(JSON.parse(JSON.stringify(siteContent)));
  const [activeTab, setActiveTab] = useState<Tab>("marca_midia");
  const [saved, setSaved] = useState(false);
  const [newCategory, setNewCategory] = useState("");

  const set = (path: string[], value: unknown) => {
    setDraft((prev) => {
      const next = JSON.parse(JSON.stringify(prev)) as Record<string, unknown>;
      let cur = next;
      for (let i = 0; i < path.length - 1; i++) {
        cur = cur[path[i]] as Record<string, unknown>;
      }
      cur[path[path.length - 1]] = value;
      return next as SiteContent;
    });
  };

  const setStatus = (key: string, field: "label" | "description", value: string) => {
    setDraft((prev) => ({
      ...prev,
      pages: {
        ...prev.pages,
        tracking: {
          ...prev.pages.tracking,
          statusLabels: field === "label"
            ? { ...prev.pages.tracking.statusLabels, [key]: value }
            : prev.pages.tracking.statusLabels,
          statusDescriptions: field === "description"
            ? { ...prev.pages.tracking.statusDescriptions, [key]: value }
            : prev.pages.tracking.statusDescriptions,
        },
      },
    }));
  };

  const handleSave = () => {
    updateSiteContent(draft);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  const handleReset = () => {
    setDraft(JSON.parse(JSON.stringify(siteContent)));
  };

  const handleResetToDefaults = () => {
    if (confirm("Redefinir todo o conteúdo para os valores padrão?")) {
      setDraft(JSON.parse(JSON.stringify(defaultSiteContent)));
    }
  };

  const addCategory = () => {
    const trimmed = newCategory.trim();
    if (!trimmed || draft.home.categories.includes(trimmed)) return;
    set(["home", "categories"], [...draft.home.categories, trimmed]);
    setNewCategory("");
  };

  const removeCategory = (cat: string) => {
    set(["home", "categories"], draft.home.categories.filter((c) => c !== cat));
  };

  // ── Status keys for tracking tab ─────────────────────────────────────────────
  const trackingStatuses = [
    { key: "pending", ptLabel: "Aguardando" },
    { key: "waiting_payment", ptLabel: "Ag. Pagamento" },
    { key: "paid", ptLabel: "Pago" },
    { key: "preparing", ptLabel: "Preparando" },
    { key: "ready_for_pickup", ptLabel: "Pronto" },
    { key: "on_the_way", ptLabel: "A caminho" },
    { key: "delivered", ptLabel: "Entregue" },
    { key: "cancelled", ptLabel: "Cancelado" },
    { key: "refunded", ptLabel: "Reembolsado" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-950">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* ── Top bar ── */}
          <div className="bg-slate-800 px-8 py-4 border-b border-slate-700 flex items-center justify-between flex-shrink-0">
            <div>
              <h2 className="text-2xl font-bold text-white">Conteúdo do Site</h2>
              <p className="text-slate-400 text-sm">Gerencie todos os textos e imagens exibidos no app</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleResetToDefaults}
                className="px-3 py-2 rounded-lg border border-slate-600 text-slate-400 hover:border-slate-500 text-sm transition-colors"
                title="Redefinir para padrões"
              >
                <RefreshCw size={15} />
              </button>
              <button
                onClick={handleReset}
                className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:border-slate-500 text-sm transition-colors"
              >
                Descartar
              </button>
              <button
                onClick={handleSave}
                className={`flex items-center gap-2 px-5 py-2 rounded-lg font-bold text-sm transition-colors ${
                  saved ? "bg-green-500 text-white" : "bg-orange-500 hover:bg-orange-600 text-white"
                }`}
              >
                <Save size={16} />
                {saved ? "Salvo!" : "Salvar alterações"}
              </button>
            </div>
          </div>

          {/* ── Tab bar ── */}
          <div className="bg-slate-800/50 border-b border-slate-700 px-8 flex-shrink-0">
            <div className="flex gap-1">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? "border-orange-500 text-orange-400"
                      : "border-transparent text-slate-400 hover:text-slate-300"
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Content area ── */}
          <div className="flex-1 overflow-auto p-8">

            {/* ═══════════════════ MARCA & MÍDIA ═══════════════════ */}
            {activeTab === "marca_midia" && (
              <div className="max-w-2xl space-y-6">
                {/* Identidade da Marca */}
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 space-y-5">
                  <div className="flex items-center gap-3 pb-3 border-b border-slate-700">
                    <Palette size={20} className="text-orange-500" />
                    <div>
                      <h3 className="text-white font-bold">Identidade da Marca</h3>
                      <p className="text-slate-400 text-sm">Nome, slogan e logo exibidos em todo o app</p>
                    </div>
                  </div>

                  <Field label="Nome do aplicativo / marca" hint="Exibido no painel admin e no cabeçalho">
                    <TextInput
                      value={draft.brand.name}
                      onChange={(v) => set(["brand", "name"], v)}
                      placeholder="Builder Pizza"
                    />
                  </Field>

                  <Field label="Slogan / tagline" hint="Frase curta de impacto exibida abaixo do nome">
                    <TextInput
                      value={draft.brand.tagline}
                      onChange={(v) => set(["brand", "tagline"], v)}
                      placeholder="A melhor pizza da cidade"
                    />
                  </Field>

                  <Field label="Título da aba do navegador" hint="Texto exibido na aba do browser (ex: Moschettieri Delivery)">
                    <TextInput
                      value={(draft.brand as typeof draft.brand & { pageTitle?: string }).pageTitle ?? ""}
                      onChange={(v) => set(["brand", "pageTitle"], v)}
                      placeholder="Pizza Delivery App"
                    />
                  </Field>

                  <ImageUpload
                    value={(draft.brand as typeof draft.brand & { faviconUrl?: string }).faviconUrl ?? ""}
                    onChange={(v) => set(["brand", "faviconUrl"], v)}
                    label="Favicon (ícone da aba do navegador)"
                    sizeGuide="Tamanho recomendado: 32×32px ou 64×64px, PNG ou ICO, máx. 50KB"
                    hint="Ícone pequeno exibido na aba do browser e favoritos."
                    maxKB={50}
                  />

                  <ImageUpload
                    value={draft.brand.logo}
                    onChange={(v) => set(["brand", "logo"], v)}
                    label="Logo da marca"
                    sizeGuide="Recomendado: 200×200px, PNG com fundo transparente, máx. 200KB"
                    hint="Exibido no painel admin e no cabeçalho da loja."
                    maxKB={200}
                    previewRounded
                  />
                </div>

                {/* Imagens do Aplicativo */}
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 space-y-6">
                  <div className="flex items-center gap-3 pb-3 border-b border-slate-700">
                    <Image size={20} className="text-orange-500" />
                    <div>
                      <h3 className="text-white font-bold">Imagens do Aplicativo</h3>
                      <p className="text-slate-400 text-sm">Imagens usadas no frontend. Deixe em branco para usar o padrão.</p>
                    </div>
                  </div>

                  <ImageUpload
                    value={draft.media.logoUrl}
                    onChange={(v) => set(["media", "logoUrl"], v)}
                    label="Logo Branco"
                    sizeGuide="Tamanho recomendado: 300×120px, PNG com fundo transparente, máx. 200KB"
                    hint="Exibido no cabeçalho da loja. Use PNG transparente para melhor resultado."
                    maxKB={200}
                  />

                  <ImageUpload
                    value={draft.media.heroBannerImage}
                    onChange={(v) => set(["media", "heroBannerImage"], v)}
                    label="Imagem do Banner (Home)"
                    sizeGuide="Tamanho recomendado: 800×300px, máx. 500KB"
                    hint="Imagem de fundo do banner promocional na página inicial."
                    maxKB={500}
                  />

                  <ImageUpload
                    value={draft.media.defaultProductImage}
                    onChange={(v) => set(["media", "defaultProductImage"], v)}
                    label="Imagem padrão de produto"
                    sizeGuide="Tamanho recomendado: 200×200px, máx. 200KB"
                    hint="Usada quando um produto não tem ícone/imagem definido."
                    maxKB={200}
                  />
                </div>

                <div className="bg-gold/10 border border-gold/30 rounded-xl p-4">
                  <p className="text-gold text-sm font-medium mb-1">Sobre as imagens</p>
                  <p className="text-gold/70 text-xs">
                    As imagens são salvas localmente na sessão. Para uso permanente em produção, utilize o upload via servidor ou serviços como <strong>Cloudinary</strong> ou <strong>ImgBB</strong>.
                  </p>
                </div>
              </div>
            )}

            {/* ═══════════════════ HOME ═══════════════════ */}
            {activeTab === "home" && (
              <div className="max-w-2xl space-y-6">
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 space-y-5">
                  <div className="flex items-center gap-3 pb-3 border-b border-slate-700">
                    <Home size={20} className="text-orange-500" />
                    <div>
                      <h3 className="text-white font-bold">Página Inicial</h3>
                      <p className="text-slate-400 text-sm">Textos da seção de produtos e banner promocional</p>
                    </div>
                  </div>

                  <Field label="Subtítulo da seção" hint="Texto menor acima do título principal">
                    <TextInput
                      value={draft.home.sectionSubtitle}
                      onChange={(v) => set(["home", "sectionSubtitle"], v)}
                      placeholder="O que você quer comer hoje?"
                    />
                  </Field>

                  <Field label="Título principal da seção" hint="Texto grande em destaque">
                    <TextInput
                      value={draft.home.sectionTitle}
                      onChange={(v) => set(["home", "sectionTitle"], v)}
                      placeholder="Escolha sua Pizza Favorita"
                    />
                  </Field>

                  <Field label="Tempo de rotação dos banners (segundos)" hint="Intervalo para troca automática entre banners de campanhas. Use 0 para desativar.">
                    <div className="flex items-center gap-3">
                      <input
                        type="number"
                        min={0}
                        max={60}
                        value={draft.home.bannerRotationInterval ?? 5}
                        onChange={(e) => set(["home", "bannerRotationInterval"], Math.max(0, parseInt(e.target.value) || 0))}
                        className="w-24 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500 text-sm"
                      />
                      <span className="text-slate-400 text-sm">segundos</span>
                      {(draft.home.bannerRotationInterval ?? 5) === 0 && (
                        <span className="text-amber-400 text-xs">Rotação desativada</span>
                      )}
                    </div>
                  </Field>

                  <Field label="Categorias do cardápio" hint="Botões de filtro acima do carrossel de produtos">
                    <div className="flex flex-wrap gap-2 mb-3 min-h-[2rem]">
                      {draft.home.categories.map((cat) => (
                        <div key={cat} className="flex items-center gap-1.5 bg-slate-700 rounded-full px-3 py-1.5">
                          <span className="text-white text-sm">{cat}</span>
                          <button
                            onClick={() => removeCategory(cat)}
                            className="text-slate-400 hover:text-red-400 transition-colors"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newCategory}
                        onChange={(e) => setNewCategory(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && addCategory()}
                        className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:outline-none focus:border-orange-500 text-sm"
                        placeholder="Nova categoria (Enter para adicionar)"
                      />
                      <button
                        onClick={addCategory}
                        className="flex items-center gap-1.5 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg transition-colors text-sm font-medium"
                      >
                        <Plus size={15} />
                        Adicionar
                      </button>
                    </div>
                  </Field>
                </div>

                <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-4">
                  <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-3">Pré-visualização</p>
                  <div className="space-y-1">
                    <p className="text-slate-400 text-sm">{draft.home.sectionSubtitle}</p>
                    <p className="text-white font-bold text-xl">{draft.home.sectionTitle}</p>
                    <div className="flex gap-2 mt-3 flex-wrap">
                      {draft.home.categories.map((c, i) => (
                        <span key={c} className={`px-3 py-1 rounded-full text-xs font-medium ${i === 0 ? "bg-orange-500 text-white" : "bg-slate-700 text-slate-300"}`}>{c}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ═══════════════════ NAVEGAÇÃO ═══════════════════ */}
            {activeTab === "nav" && (
              <div className="max-w-2xl space-y-6">
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 space-y-5">
                  <div className="flex items-center gap-3 pb-3 border-b border-slate-700">
                    <Navigation size={20} className="text-orange-500" />
                    <div>
                      <h3 className="text-white font-bold">Barra de Navegação</h3>
                      <p className="text-slate-400 text-sm">Rótulos dos botões do menu inferior</p>
                    </div>
                  </div>

                  {(["home", "cart", "orders", "account"] as const).map((key) => {
                    const icons: Record<string, string> = { home: "🏠", cart: "🛒", orders: "📦", account: "👤" };
                    const placeholders: Record<string, string> = { home: "Home", cart: "Carrinho", orders: "Pedidos", account: "Conta" };
                    return (
                      <Field key={key} label={`${icons[key]} Ícone "${key}"`}>
                        <TextInput
                          value={draft.nav[key]}
                          onChange={(v) => set(["nav", key], v)}
                          placeholder={placeholders[key]}
                        />
                      </Field>
                    );
                  })}
                </div>

                {/* Preview */}
                <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-4">
                  <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-3">Pré-visualização da barra</p>
                  <div className="bg-orange-500 rounded-full py-3 px-6 flex justify-around items-center">
                    {(["home", "cart", "orders", "account"] as const).map((key, i) => {
                      const icons: Record<string, string> = { home: "🏠", cart: "🛒", orders: "📦", account: "👤" };
                      return (
                        <div key={key} className={`flex flex-col items-center gap-0.5 ${i === 0 ? "text-white" : "text-white/60"}`}>
                          <span className="text-lg">{icons[key]}</span>
                          <span className="text-xs font-medium">{draft.nav[key]}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ═══════════════════ PÁGINAS ═══════════════════ */}
            {activeTab === "paginas" && (
              <div className="max-w-2xl space-y-4">

                {/* Cart */}
                <Section icon={<span className="text-lg">🛒</span>} title="Carrinho" subtitle="Textos da página do carrinho de compras" defaultOpen>
                  <Field label="Título da página">
                    <TextInput value={draft.pages.cart.title} onChange={(v) => set(["pages", "cart", "title"], v)} placeholder="Meu Carrinho" />
                  </Field>
                  <Field label="Título — carrinho vazio">
                    <TextInput value={draft.pages.cart.emptyTitle} onChange={(v) => set(["pages", "cart", "emptyTitle"], v)} placeholder="Carrinho vazio" />
                  </Field>
                  <Field label="Subtítulo — carrinho vazio">
                    <TextInput value={draft.pages.cart.emptySubtitle} onChange={(v) => set(["pages", "cart", "emptySubtitle"], v)} placeholder="Adicione pizzas deliciosas para começar!" />
                  </Field>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Botão finalizar pedido">
                      <TextInput value={draft.pages.cart.checkoutButton} onChange={(v) => set(["pages", "cart", "checkoutButton"], v)} placeholder="Finalizar Pedido" />
                    </Field>
                    <Field label="Botão ir ao cardápio">
                      <TextInput value={draft.pages.cart.menuButton} onChange={(v) => set(["pages", "cart", "menuButton"], v)} placeholder="Ver cardápio" />
                    </Field>
                  </div>
                </Section>

                {/* Checkout */}
                <Section icon={<span className="text-lg">💳</span>} title="Checkout" subtitle="Textos da página de finalização de pedido">
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título da página">
                      <TextInput value={draft.pages.checkout.title} onChange={(v) => set(["pages", "checkout", "title"], v)} placeholder="Checkout" />
                    </Field>
                    <Field label="Botão confirmar">
                      <TextInput value={draft.pages.checkout.confirmButton} onChange={(v) => set(["pages", "checkout", "confirmButton"], v)} placeholder="Confirmar Pedido" />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título seção endereço">
                      <TextInput value={draft.pages.checkout.deliveryTitle} onChange={(v) => set(["pages", "checkout", "deliveryTitle"], v)} placeholder="Endereço de Entrega" />
                    </Field>
                    <Field label="Título seção resumo">
                      <TextInput value={draft.pages.checkout.summaryTitle} onChange={(v) => set(["pages", "checkout", "summaryTitle"], v)} placeholder="Resumo do Pedido" />
                    </Field>
                  </div>
                  <div className="border-t border-slate-700 pt-4">
                    <p className="text-slate-300 text-xs font-bold uppercase tracking-wider mb-3">Placeholders dos campos</p>
                    <div className="space-y-3">
                      {(["name", "phone", "address", "city", "complement"] as const).map((f) => {
                        const labels: Record<string, string> = { name: "Nome", phone: "Telefone", address: "Endereço", city: "Cidade", complement: "Complemento" };
                        return (
                          <Field key={f} label={labels[f]}>
                            <TextInput
                              value={draft.pages.checkout.fields[f]}
                              onChange={(v) => setDraft((prev) => ({
                                ...prev,
                                pages: { ...prev.pages, checkout: { ...prev.pages.checkout, fields: { ...prev.pages.checkout.fields, [f]: v } } },
                              }))}
                            />
                          </Field>
                        );
                      })}
                    </div>
                  </div>
                </Section>

                {/* Product */}
                <Section icon={<span className="text-lg">🍕</span>} title="Página de Produto" subtitle="Textos da montagem de pizza">
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título da página">
                      <TextInput value={draft.pages.product.pageTitle} onChange={(v) => set(["pages", "product", "pageTitle"], v)} placeholder="Monte sua Pizza" />
                    </Field>
                    <Field label="Botão adicionar ao carrinho">
                      <TextInput value={draft.pages.product.addToCartButton} onChange={(v) => set(["pages", "product", "addToCartButton"], v)} placeholder="Adicionar ao Carrinho" />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Rótulo seção divisão">
                      <TextInput value={draft.pages.product.divisionLabel} onChange={(v) => set(["pages", "product", "divisionLabel"], v)} placeholder="Divisão da Pizza" />
                    </Field>
                    <Field label="Rótulo seção tamanho">
                      <TextInput value={draft.pages.product.sizeLabel} onChange={(v) => set(["pages", "product", "sizeLabel"], v)} placeholder="Tamanho da Pizza" />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Rótulo seção adicionais">
                      <TextInput value={draft.pages.product.addOnsLabel} onChange={(v) => set(["pages", "product", "addOnsLabel"], v)} placeholder="Adicionais (opcional)" />
                    </Field>
                    <Field label="Rótulo seção quantidade">
                      <TextInput value={draft.pages.product.quantityLabel} onChange={(v) => set(["pages", "product", "quantityLabel"], v)} placeholder="Quantidade" />
                    </Field>
                  </div>
                </Section>

                {/* Pedidos */}
                <Section icon={<span className="text-lg">📦</span>} title="Meus Pedidos" subtitle="Textos da lista de pedidos do cliente">
                  <Field label="Título da página">
                    <TextInput value={draft.pages.pedidos.title} onChange={(v) => set(["pages", "pedidos", "title"], v)} placeholder="Meus Pedidos" />
                  </Field>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título — sem pedidos">
                      <TextInput value={draft.pages.pedidos.emptyTitle} onChange={(v) => set(["pages", "pedidos", "emptyTitle"], v)} placeholder="Nenhum pedido ainda" />
                    </Field>
                    <Field label="Botão fazer pedido">
                      <TextInput value={draft.pages.pedidos.orderButton} onChange={(v) => set(["pages", "pedidos", "orderButton"], v)} placeholder="Fazer pedido" />
                    </Field>
                  </div>
                  <Field label="Subtítulo — sem pedidos">
                    <TextInput value={draft.pages.pedidos.emptySubtitle} onChange={(v) => set(["pages", "pedidos", "emptySubtitle"], v)} placeholder="Seus pedidos aparecerão aqui após a primeira compra." />
                  </Field>
                </Section>

                {/* Conta */}
                <Section icon={<span className="text-lg">👤</span>} title="Minha Conta" subtitle="Textos da página de perfil do cliente">
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título da página">
                      <TextInput value={draft.pages.conta.title} onChange={(v) => set(["pages", "conta", "title"], v)} placeholder="Minha Conta" />
                    </Field>
                    <Field label="Botão sair">
                      <TextInput value={draft.pages.conta.logoutButton} onChange={(v) => set(["pages", "conta", "logoutButton"], v)} placeholder="Sair da conta" />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título dados pessoais">
                      <TextInput value={draft.pages.conta.personalDataTitle} onChange={(v) => set(["pages", "conta", "personalDataTitle"], v)} placeholder="Dados pessoais" />
                    </Field>
                    <Field label="Título atalhos">
                      <TextInput value={draft.pages.conta.shortcutsTitle} onChange={(v) => set(["pages", "conta", "shortcutsTitle"], v)} placeholder="Atalhos" />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Estatística — pedidos realizados">
                      <TextInput value={draft.pages.conta.statsOrders} onChange={(v) => set(["pages", "conta", "statsOrders"], v)} placeholder="Pedidos realizados" />
                    </Field>
                    <Field label="Estatística — total gasto">
                      <TextInput value={draft.pages.conta.statsSpent} onChange={(v) => set(["pages", "conta", "statsSpent"], v)} placeholder="Total gasto" />
                    </Field>
                  </div>
                </Section>

                {/* Fidelidade */}
                <Section icon={<span className="text-lg">🏆</span>} title="Fidelidade" subtitle="Textos do programa de pontos">
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título da página">
                      <TextInput value={draft.pages.fidelidade.title} onChange={(v) => set(["pages", "fidelidade", "title"], v)} placeholder="Programa de Fidelidade" />
                    </Field>
                    <Field label="Unidade de pontos">
                      <TextInput value={draft.pages.fidelidade.pointsUnit} onChange={(v) => set(["pages", "fidelidade", "pointsUnit"], v)} placeholder="pts" />
                    </Field>
                  </div>
                  <Field label="Botão resgatar">
                    <TextInput value={draft.pages.fidelidade.redeemButton} onChange={(v) => set(["pages", "fidelidade", "redeemButton"], v)} placeholder="Resgatar" />
                  </Field>
                </Section>

                {/* Cupons */}
                <Section icon={<span className="text-lg">🎟️</span>} title="Cupons" subtitle="Textos da página de cupons de desconto">
                  <Field label="Título da página">
                    <TextInput value={draft.pages.cupons.title} onChange={(v) => set(["pages", "cupons", "title"], v)} placeholder="Meus Cupons" />
                  </Field>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Texto — sem cupons">
                      <TextInput value={draft.pages.cupons.emptyText} onChange={(v) => set(["pages", "cupons", "emptyText"], v)} placeholder="Você não possui cupons ativos." multiline />
                    </Field>
                    <div className="space-y-4">
                      <Field label="Botão copiar código">
                        <TextInput value={draft.pages.cupons.copyButton} onChange={(v) => set(["pages", "cupons", "copyButton"], v)} placeholder="Copiar" />
                      </Field>
                      <Field label="Rótulo cupom utilizado">
                        <TextInput value={draft.pages.cupons.usedLabel} onChange={(v) => set(["pages", "cupons", "usedLabel"], v)} placeholder="Utilizado" />
                      </Field>
                    </div>
                  </div>
                </Section>
              </div>
            )}

            {/* ═══════════════════ RASTREAMENTO ═══════════════════ */}
            {activeTab === "rastreamento" && (
              <div className="max-w-3xl space-y-6">
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 space-y-4">
                  <div className="flex items-center gap-3 pb-3 border-b border-slate-700">
                    <Activity size={20} className="text-orange-500" />
                    <div>
                      <h3 className="text-white font-bold">Textos Gerais</h3>
                      <p className="text-slate-400 text-sm">Cabeçalhos da página de acompanhamento de pedido</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Título da página">
                      <TextInput value={draft.pages.tracking.pageTitle} onChange={(v) => set(["pages", "tracking", "pageTitle"], v)} placeholder="Acompanhar Pedido" />
                    </Field>
                    <Field label="Rótulo número do pedido">
                      <TextInput value={draft.pages.tracking.orderNumberLabel} onChange={(v) => set(["pages", "tracking", "orderNumberLabel"], v)} placeholder="Número do Pedido" />
                    </Field>
                  </div>
                  <Field label="Texto de tempo estimado" hint='Use {time} como variável para o número de minutos — ex: "será entregue em {time} minutos"'>
                    <TextInput value={draft.pages.tracking.estimatedTimeText} onChange={(v) => set(["pages", "tracking", "estimatedTimeText"], v)} placeholder="será entregue em {time} minutos" />
                  </Field>
                </div>

                <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                  <div className="px-6 py-4 border-b border-slate-700 flex items-center gap-3">
                    <Activity size={18} className="text-orange-500" />
                    <div>
                      <h3 className="text-white font-bold">Rótulos e Descrições por Status</h3>
                      <p className="text-slate-400 text-sm">Texto exibido em cada etapa do ciclo de vida do pedido</p>
                    </div>
                  </div>
                  <div className="divide-y divide-slate-700">
                    {trackingStatuses.map(({ key, ptLabel }) => (
                      <div key={key} className="px-6 py-4 grid grid-cols-2 gap-4 items-start">
                        <div>
                          <p className="text-slate-400 text-xs font-mono mb-1.5">
                            <span className="bg-slate-700 px-1.5 py-0.5 rounded text-orange-400">{key}</span>
                            {" "}· {ptLabel}
                          </p>
                          <Field label="Rótulo do status">
                            <TextInput
                              value={draft.pages.tracking.statusLabels[key] ?? ""}
                              onChange={(v) => setStatus(key, "label", v)}
                              placeholder={ptLabel}
                            />
                          </Field>
                        </div>
                        <Field label="Descrição ao cliente">
                          <TextInput
                            value={draft.pages.tracking.statusDescriptions[key] ?? ""}
                            onChange={(v) => setStatus(key, "description", v)}
                            placeholder="Descreva o que acontece neste estado..."
                            multiline
                          />
                        </Field>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}


          </div>
        </div>
      </div>
    </div>
  );
}
