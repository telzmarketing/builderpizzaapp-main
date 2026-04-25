import { useState, useEffect, useCallback } from "react";
import {
  Plus, Trash2, Edit2, Sparkles, Package, Tag, BarChart2,
  X, ExternalLink, Star,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import ImageUpload from "@/components/admin/ImageUpload";
import {
  campaignsApi, productsApi, couponsApi, promotionsApi,
  type ApiCampaign, type ApiCampaignProduct, type ApiPromotionalKit,
  type ApiProduct, type ApiCoupon, type ApiCouponUsage, type ApiPromotion,
  type CampaignStatus, type CampaignType, type CpDiscountType, type KitType,
} from "@/lib/api";

// ── Shared mini components ────────────────────────────────────────────────────

const Inp = ({ label, ...p }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) => (
  <div>
    <label className="block text-parchment text-xs font-medium mb-1">{label}</label>
    <input {...p} className={"w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold " + (p.className ?? "")} />
  </div>
);

const Sel = ({ label, children, ...p }: { label: string } & React.SelectHTMLAttributes<HTMLSelectElement> & { children: React.ReactNode }) => (
  <div>
    <label className="block text-parchment text-xs font-medium mb-1">{label}</label>
    <select {...p} className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold">
      {children}
    </select>
  </div>
);

const Txt = ({ label, ...p }: { label: string } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <div>
    <label className="block text-parchment text-xs font-medium mb-1">{label}</label>
    <textarea {...p} className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold resize-none" />
  </div>
);

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="bg-surface-01 rounded-2xl border border-surface-03 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-03">
          <h3 className="text-cream font-bold text-lg">{title}</h3>
          <button onClick={onClose} className="text-stone hover:text-cream transition-colors"><X size={20} /></button>
        </div>
        <div className="px-6 py-4">{children}</div>
      </div>
    </div>
  );
}

function SaveBtn({ loading, label = "Salvar" }: { loading?: boolean; label?: string }) {
  return (
    <button type="submit" disabled={loading} className="flex-1 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
      {loading ? "Salvando..." : label}
    </button>
  );
}

const STATUS_LABEL: Record<CampaignStatus, string> = { draft: "Rascunho", active: "Ativa", paused: "Pausada", ended: "Encerrada" };
const STATUS_COLOR: Record<CampaignStatus, string> = {
  draft: "bg-stone/20 text-stone border-stone/30",
  active: "bg-green-500/20 text-green-400 border-green-500/30",
  paused: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  ended: "bg-red-500/20 text-red-400 border-red-500/30",
};

// ── Main Component ─────────────────────────────────────────────────────────────

type Tab = "cupons" | "campanhas" | "kits" | "uso_cupons";

// ── Forms ──────────────────────────────────────────────────────────────────────

interface PromotionForm {
  title: string; subtitle: string; icon: string; description: string;
  validity_text: string; valid_from: string; valid_until: string; active: boolean;
}

interface CouponForm {
  code: string; description: string; icon: string;
  coupon_type: "percentage" | "fixed";
  discount_value: number; min_order_value: number;
  max_uses: string; expiry_date: string; active: boolean;
}

interface CampaignForm {
  name: string; description: string; status: CampaignStatus;
  start_at: string; end_at: string; banner: string; slug: string;
  campaign_type: CampaignType; display_title: string; display_subtitle: string;
  display_order: number; published: boolean; schedule_enabled: boolean;
}

interface KitForm {
  name: string; description: string; icon: string; kit_type: KitType;
  price_original: number; price_promotional: number;
  discount_type: CpDiscountType | ""; discount_value: number;
  valid_until: string; active: boolean;
}

const emptyPromoForm: PromotionForm = {
  title: "", subtitle: "", icon: "", description: "",
  validity_text: "", valid_from: "", valid_until: "", active: true,
};

const emptyCouponForm: CouponForm = {
  code: "", description: "", icon: "🎟️",
  coupon_type: "percentage", discount_value: 10, min_order_value: 0,
  max_uses: "", expiry_date: "", active: true,
};

const emptyCampaignForm: CampaignForm = {
  name: "", description: "", status: "draft", start_at: "", end_at: "",
  banner: "", slug: "", campaign_type: "products_promo",
  display_title: "", display_subtitle: "", display_order: 0, published: false,
  schedule_enabled: false,
};

const emptyKitForm: KitForm = {
  name: "", description: "", icon: "🎁", kit_type: "kit",
  price_original: 0, price_promotional: 0,
  discount_type: "", discount_value: 0, valid_until: "", active: true,
};

export default function AdminCampanhas() {
  const [activeTab, setActiveTab] = useState<Tab>("campanhas");

  // ── Data ───────────────────────────────────────────────────────────────────
  const [promotionsList, setPromotionsList] = useState<ApiPromotion[]>([]);
  const [campaigns, setCampaigns] = useState<ApiCampaign[]>([]);
  const [kits, setKits] = useState<ApiPromotionalKit[]>([]);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [usage, setUsage] = useState<ApiCouponUsage[]>([]);
  const [couponsList, setCouponsList] = useState<ApiCoupon[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  // ── Promotion modal ────────────────────────────────────────────────────────
  const [showPromoModal, setShowPromoModal] = useState(false);
  const [editingPromoId, setEditingPromoId] = useState<string | null>(null);
  const [promoForm, setPromoForm] = useState<PromotionForm>(emptyPromoForm);
  const [promoSaving, setPromoSaving] = useState(false);

  // ── Coupon modal ───────────────────────────────────────────────────────────
  const [showCouponModal, setShowCouponModal] = useState(false);
  const [editingCouponId, setEditingCouponId] = useState<string | null>(null);
  const [couponForm, setCouponForm] = useState<CouponForm>(emptyCouponForm);
  const [couponSaving, setCouponSaving] = useState(false);

  // ── Campaign modal ─────────────────────────────────────────────────────────
  const [showCampaignModal, setShowCampaignModal] = useState(false);
  const [editingCampaignId, setEditingCampaignId] = useState<string | null>(null);
  const [campaignForm, setCampaignForm] = useState<CampaignForm>(emptyCampaignForm);
  const [campaignSaving, setCampaignSaving] = useState(false);

  // ── Campaign products modal ────────────────────────────────────────────────
  const [selectedCampaign, setSelectedCampaign] = useState<ApiCampaign | null>(null);
  const [cpList, setCpList] = useState<ApiCampaignProduct[]>([]);
  const [showCpModal, setShowCpModal] = useState(false);
  const [newCpProductIds, setNewCpProductIds] = useState<string[]>([]);
  const [newCpPrice, setNewCpPrice] = useState("");
  const [newCpDiscType, setNewCpDiscType] = useState<CpDiscountType | "">("");
  const [newCpDiscVal, setNewCpDiscVal] = useState("");

  // ── Kit modal ──────────────────────────────────────────────────────────────
  const [showKitModal, setShowKitModal] = useState(false);
  const [editingKitId, setEditingKitId] = useState<string | null>(null);
  const [kitForm, setKitForm] = useState<KitForm>(emptyKitForm);
  const [kitSaving, setKitSaving] = useState(false);
  const [selectedKit, setSelectedKit] = useState<ApiPromotionalKit | null>(null);
  const [showKitItemsModal, setShowKitItemsModal] = useState(false);
  const [newKitItemProductId, setNewKitItemProductId] = useState("");
  const [newKitItemQty, setNewKitItemQty] = useState(1);

  const [toast, setToast] = useState("");
  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  const loadAll = useCallback(async () => {
    setLoadingData(true);
    try {
      const [promos, c, k, p, u, cps] = await Promise.all([
        promotionsApi.list(false),
        campaignsApi.list(),
        campaignsApi.listKits(),
        productsApi.list(false),
        couponsApi.listUsage(),
        couponsApi.list(),
      ]);
      setPromotionsList(promos);
      setCampaigns(c);
      setKits(k);
      setProducts(p);
      setUsage(u);
      setCouponsList(cps);
    } catch { /* ignore */ }
    finally { setLoadingData(false); }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ── Promotion CRUD ──────────────────────────────────────────────────────────

  const openCreatePromo = () => {
    setEditingPromoId(null);
    setPromoForm(emptyPromoForm);
    setShowPromoModal(true);
  };

  const openEditPromo = (p: ApiPromotion) => {
    setEditingPromoId(p.id);
    setPromoForm({
      title: p.title, subtitle: p.subtitle ?? "", icon: p.icon,
      description: p.description ?? "", validity_text: p.validity_text ?? "",
      valid_from: p.valid_from ? p.valid_from.slice(0, 16) : "",
      valid_until: p.valid_until ? p.valid_until.slice(0, 16) : "",
      active: p.active,
    });
    setShowPromoModal(true);
  };

  const handleSavePromo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promoForm.title.trim()) { showToast("Título é obrigatório."); return; }
    setPromoSaving(true);
    try {
      const payload = {
        title: promoForm.title,
        subtitle: promoForm.subtitle || null,
        icon: promoForm.icon || "⭐",
        description: promoForm.description || null,
        validity_text: promoForm.validity_text || null,
        valid_from: promoForm.valid_from ? new Date(promoForm.valid_from).toISOString() : null,
        valid_until: promoForm.valid_until ? new Date(promoForm.valid_until).toISOString() : null,
        active: promoForm.active,
      };
      if (editingPromoId) {
        await promotionsApi.update(editingPromoId, payload);
        showToast("Promoção atualizada!");
      } else {
        await promotionsApi.create(payload as any);
        showToast("Promoção criada!");
      }
      setShowPromoModal(false);
      loadAll();
    } catch { showToast("Erro ao salvar."); }
    finally { setPromoSaving(false); }
  };

  const deletePromo = async (id: string) => {
    if (!confirm("Excluir esta promoção?")) return;
    try {
      await promotionsApi.remove(id);
      showToast("Promoção removida.");
      loadAll();
    } catch { showToast("Erro ao excluir."); }
  };

  // ── Coupon CRUD ─────────────────────────────────────────────────────────────

  const openCreateCoupon = () => {
    setEditingCouponId(null);
    setCouponForm(emptyCouponForm);
    setShowCouponModal(true);
  };

  const openEditCoupon = (c: ApiCoupon) => {
    setEditingCouponId(c.id);
    setCouponForm({
      code: c.code, description: c.description ?? "", icon: c.icon,
      coupon_type: c.coupon_type, discount_value: c.discount_value,
      min_order_value: c.min_order_value,
      max_uses: c.max_uses !== null ? String(c.max_uses) : "",
      expiry_date: c.expiry_date ? c.expiry_date.slice(0, 16) : "",
      active: c.active,
    });
    setShowCouponModal(true);
  };

  const handleSaveCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!couponForm.code.trim()) { showToast("Código é obrigatório."); return; }
    setCouponSaving(true);
    try {
      const payload = {
        code: couponForm.code.trim().toUpperCase(),
        description: couponForm.description || null,
        icon: couponForm.icon || "🎟️",
        coupon_type: couponForm.coupon_type,
        discount_value: couponForm.discount_value,
        min_order_value: couponForm.min_order_value,
        max_uses: couponForm.max_uses ? parseInt(couponForm.max_uses) : null,
        expiry_date: couponForm.expiry_date ? new Date(couponForm.expiry_date).toISOString() : null,
        active: couponForm.active,
      };
      if (editingCouponId) {
        await couponsApi.update(editingCouponId, payload);
        showToast("Cupom atualizado!");
      } else {
        await couponsApi.create(payload as any);
        showToast("Cupom criado!");
      }
      setShowCouponModal(false);
      loadAll();
    } catch { showToast("Erro ao salvar."); }
    finally { setCouponSaving(false); }
  };

  const deleteCoupon = async (id: string) => {
    if (!confirm("Excluir este cupom?")) return;
    try {
      await couponsApi.remove(id);
      showToast("Cupom removido.");
      loadAll();
    } catch { showToast("Erro ao excluir."); }
  };

  // ── Campaign CRUD ──────────────────────────────────────────────────────────

  const openCreateCampaign = () => {
    setEditingCampaignId(null);
    setCampaignForm(emptyCampaignForm);
    setShowCampaignModal(true);
  };

  const openEditCampaign = (c: ApiCampaign) => {
    setEditingCampaignId(c.id);
    setCampaignForm({
      name: c.name, description: c.description ?? "", status: c.status,
      start_at: c.start_at ? c.start_at.slice(0, 16) : "",
      end_at: c.end_at ? c.end_at.slice(0, 16) : "",
      banner: c.banner ?? "", slug: c.slug,
      campaign_type: c.campaign_type, display_title: c.display_title ?? "",
      display_subtitle: c.display_subtitle ?? "",
      display_order: c.display_order, published: c.published,
      schedule_enabled: Boolean(c.start_at || c.end_at),
    });
    setShowCampaignModal(true);
  };

  const handleSaveCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campaignForm.name.trim() || !campaignForm.slug.trim()) {
      showToast("Nome e slug são obrigatórios.");
      return;
    }
    if (campaignForm.schedule_enabled && !campaignForm.start_at && !campaignForm.end_at) {
      showToast("Informe inicio ou termino para agendar a campanha.");
      return;
    }
    if (campaignForm.start_at && campaignForm.end_at && new Date(campaignForm.end_at) <= new Date(campaignForm.start_at)) {
      showToast("O termino deve ser depois do inicio.");
      return;
    }
    setCampaignSaving(true);
    try {
      const { schedule_enabled, ...formData } = campaignForm;
      const payload = {
        ...formData,
        start_at: schedule_enabled && campaignForm.start_at ? new Date(campaignForm.start_at).toISOString() : null,
        end_at: schedule_enabled && campaignForm.end_at ? new Date(campaignForm.end_at).toISOString() : null,
        description: campaignForm.description || null,
        banner: campaignForm.banner || null,
        display_title: campaignForm.display_title || null,
        display_subtitle: campaignForm.display_subtitle || null,
      };
      if (editingCampaignId) {
        await campaignsApi.update(editingCampaignId, payload as any);
        showToast("Campanha atualizada!");
      } else {
        await campaignsApi.create(payload as any);
        showToast("Campanha criada!");
      }
      setShowCampaignModal(false);
      loadAll();
    } catch (err: any) {
      showToast(err?.message ?? "Erro ao salvar.");
    } finally { setCampaignSaving(false); }
  };

  const deleteCampaign = async (id: string) => {
    if (!confirm("Excluir esta campanha?")) return;
    try {
      await campaignsApi.remove(id);
      showToast("Campanha removida.");
      loadAll();
    } catch { showToast("Erro ao excluir."); }
  };

  // ── Campaign Products ──────────────────────────────────────────────────────

  const openCampaignProducts = async (c: ApiCampaign) => {
    setSelectedCampaign(c);
    const list = await campaignsApi.listProducts(c.id);
    setCpList(list);
    setNewCpProductIds([]);
    setShowCpModal(true);
  };

  const toggleCampaignProductSelection = (productId: string) => {
    setNewCpProductIds((current) =>
      current.includes(productId)
        ? current.filter((id) => id !== productId)
        : [...current, productId]
    );
  };

  const handleAddCampaignProduct = async () => {
    if (!selectedCampaign || newCpProductIds.length === 0) return;
    try {
      await Promise.all(newCpProductIds.map((productId) =>
        campaignsApi.addProduct(selectedCampaign.id, {
          product_id: productId,
          kit_id: null,
          promotional_price: newCpPrice ? parseFloat(newCpPrice) : null,
          discount_type: (newCpDiscType as CpDiscountType) || null,
          discount_value: newCpDiscVal ? parseFloat(newCpDiscVal) : null,
          active: true,
        })
      ));
      const list = await campaignsApi.listProducts(selectedCampaign.id);
      setCpList(list);
      setNewCpProductIds([]); setNewCpPrice(""); setNewCpDiscType(""); setNewCpDiscVal("");
      showToast(newCpProductIds.length > 1 ? "Produtos adicionados!" : "Produto adicionado!");
    } catch { showToast("Erro ao adicionar produto."); }
  };

  const handleRemoveCampaignProduct = async (cpId: string) => {
    if (!selectedCampaign) return;
    try {
      await campaignsApi.removeProduct(cpId);
      const list = await campaignsApi.listProducts(selectedCampaign.id);
      setCpList(list);
      showToast("Produto removido.");
    } catch { showToast("Erro ao remover."); }
  };

  // ── Kit CRUD ───────────────────────────────────────────────────────────────

  const openCreateKit = () => {
    setEditingKitId(null);
    setKitForm(emptyKitForm);
    setShowKitModal(true);
  };

  const openEditKit = (k: ApiPromotionalKit) => {
    setEditingKitId(k.id);
    setKitForm({
      name: k.name, description: k.description ?? "", icon: k.icon,
      kit_type: k.kit_type, price_original: k.price_original, price_promotional: k.price_promotional,
      discount_type: k.discount_type ?? "", discount_value: k.discount_value ?? 0,
      valid_until: k.valid_until ? k.valid_until.slice(0, 16) : "", active: k.active,
    });
    setShowKitModal(true);
  };

  const handleSaveKit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!kitForm.name.trim()) { showToast("Nome é obrigatório."); return; }
    setKitSaving(true);
    try {
      const payload = {
        ...kitForm,
        discount_type: (kitForm.discount_type as CpDiscountType) || null,
        discount_value: kitForm.discount_value || null,
        valid_until: kitForm.valid_until ? new Date(kitForm.valid_until).toISOString() : null,
        description: kitForm.description || null,
      };
      if (editingKitId) {
        await campaignsApi.updateKit(editingKitId, payload as any);
        showToast("Kit atualizado!");
      } else {
        await campaignsApi.createKit(payload as any);
        showToast("Kit criado!");
      }
      setShowKitModal(false);
      loadAll();
    } catch { showToast("Erro ao salvar."); }
    finally { setKitSaving(false); }
  };

  const deleteKit = async (id: string) => {
    if (!confirm("Excluir este kit?")) return;
    try {
      await campaignsApi.removeKit(id);
      showToast("Kit removido.");
      loadAll();
    } catch { showToast("Erro ao excluir."); }
  };

  const openKitItems = (k: ApiPromotionalKit) => {
    setSelectedKit(k);
    setShowKitItemsModal(true);
  };

  const handleAddKitItem = async () => {
    if (!selectedKit || !newKitItemProductId) return;
    try {
      await campaignsApi.addKitItem(selectedKit.id, newKitItemProductId, newKitItemQty);
      const refreshed = await campaignsApi.listKits();
      setKits(refreshed);
      const updated = refreshed.find((k) => k.id === selectedKit.id);
      if (updated) setSelectedKit(updated);
      setNewKitItemProductId(""); setNewKitItemQty(1);
      showToast("Item adicionado!");
    } catch { showToast("Erro ao adicionar item."); }
  };

  const handleRemoveKitItem = async (itemId: string) => {
    if (!selectedKit) return;
    try {
      await campaignsApi.removeKitItem(itemId);
      const refreshed = await campaignsApi.listKits();
      setKits(refreshed);
      const updated = refreshed.find((k) => k.id === selectedKit.id);
      if (updated) setSelectedKit(updated);
      showToast("Item removido.");
    } catch { showToast("Erro ao remover item."); }
  };

  // ── Helpers ────────────────────────────────────────────────────────────────

  const getProductName = (id: string) => products.find((p) => p.id === id)?.name ?? id;
  const getCouponCode = (id: string) => couponsList.find((c) => c.id === id)?.code ?? id;

  // ── Render ─────────────────────────────────────────────────────────────────

  const tabs: { key: Tab; icon: React.ReactNode; label: string }[] = [
    { key: "campanhas", icon: <Sparkles size={14} />, label: "Campanhas" },
    { key: "cupons", icon: <Tag size={14} />, label: "Cupons" },
    { key: "kits", icon: <Package size={14} />, label: "Kits Promocionais" },
    { key: "uso_cupons", icon: <BarChart2 size={14} />, label: "Uso de Cupons" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      {toast && (
        <div className="fixed top-4 right-4 z-[100] bg-surface-02 border border-gold/40 text-cream px-4 py-2 rounded-lg shadow-lg text-sm">
          {toast}
        </div>
      )}

      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 sticky top-0 z-20">
            <h2 className="text-2xl font-bold text-cream">Campanhas</h2>
            <p className="text-stone text-sm">{campaigns.length} campanhas · {promotionsList.length} banners · {couponsList.length} cupons · {kits.length} kits</p>
          </div>

          {/* Tabs */}
          <div className="px-8 pt-4 flex gap-2 flex-wrap">
            {tabs.map(({ key, icon, label }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all ${activeTab === key ? "bg-gold text-cream" : "bg-surface-02 text-parchment hover:bg-surface-03 border border-surface-03"}`}
              >
                {icon}
                {label}
              </button>
            ))}
          </div>

          <div className="p-8">
            {loadingData ? (
              <div className="text-center py-16 text-stone">Carregando...</div>
            ) : (
              <>
                {/* ── TAB: CUPONS ────────────────────────────────────────────── */}
                {activeTab === "cupons" && (
                  <>
                    <div className="flex justify-end mb-6">
                      <button
                        onClick={openCreateCoupon}
                        className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm"
                      >
                        <Plus size={16} />
                        Novo Cupom
                      </button>
                    </div>

                    <div className="space-y-4">
                      {couponsList.map((c) => {
                        const discountLabel =
                          c.coupon_type === "percentage" ? `${c.discount_value}% OFF`
                          : `R$ ${c.discount_value.toFixed(2)} OFF`;
                        return (
                          <div key={c.id} className={`bg-surface-02 rounded-xl border border-surface-03 overflow-hidden ${!c.active ? "opacity-60" : ""}`}>
                            <div className="flex items-center gap-4 p-4">
                              <div className="w-12 h-12 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-2xl">
                                {c.icon}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-gold font-mono font-bold text-sm">{c.code}</span>
                                  <span className="text-xs bg-gold/20 text-gold px-2 py-0.5 rounded-full border border-gold/30">{discountLabel}</span>
                                  <span className={`text-xs px-2 py-0.5 rounded-full border ${c.active ? "bg-green-500/20 text-green-400 border-green-500/30" : "bg-stone/20 text-stone border-stone/30"}`}>
                                    {c.active ? "Ativo" : "Inativo"}
                                  </span>
                                </div>
                                <div className="flex gap-3 mt-0.5 text-xs text-stone flex-wrap">
                                  {c.min_order_value > 0 && <span>Mínimo: R$ {c.min_order_value.toFixed(2)}</span>}
                                  {c.max_uses !== null && <span>Usos: {c.used_count}/{c.max_uses}</span>}
                                  {c.expiry_date && <span>Validade: {new Date(c.expiry_date).toLocaleDateString("pt-BR")}</span>}
                                  {c.description && <span>{c.description}</span>}
                                </div>
                              </div>
                              <div className="flex gap-2 flex-shrink-0">
                                <button
                                  onClick={() => openEditCoupon(c)}
                                  className="p-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors"
                                >
                                  <Edit2 size={14} />
                                </button>
                                <button
                                  onClick={() => deleteCoupon(c.id)}
                                  className="p-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {couponsList.length === 0 && (
                      <div className="text-center py-16">
                        <Tag size={48} className="text-slate-600 mx-auto mb-4" />
                        <p className="text-stone text-lg">Nenhum cupom criado</p>
                        <button onClick={openCreateCoupon} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
                          <Plus size={16} /> Criar Primeiro Cupom
                        </button>
                      </div>
                    )}
                  </>
                )}

                {/* ── TAB: CAMPANHAS ─────────────────────────────────────────── */}
                {activeTab === "campanhas" && (
                  <>
                    <div className="flex justify-end mb-6">
                      <button
                        onClick={openCreateCampaign}
                        className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm"
                      >
                        <Plus size={16} />
                        Nova Campanha
                      </button>
                    </div>

                    <div className="space-y-4">
                      {campaigns.map((c) => (
                        <div key={c.id} className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                          <div className="flex items-center gap-4 p-4">
                            <div className="w-14 h-14 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center overflow-hidden">
                              {c.banner ? (
                                c.banner.startsWith("http") || c.banner.startsWith("data:") ? (
                                  <img src={c.banner} className="w-full h-full object-cover" alt={c.name} />
                                ) : (
                                  <span className="text-2xl">{c.banner}</span>
                                )
                              ) : <Sparkles size={24} className="text-gold" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="text-cream font-bold text-sm">{c.name}</h3>
                                <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLOR[c.status]}`}>
                                  {STATUS_LABEL[c.status]}
                                </span>
                                {c.published && (
                                  <span className="text-xs px-2 py-0.5 rounded-full bg-gold/20 text-gold border border-gold/30">
                                    Publicada
                                  </span>
                                )}
                              </div>
                              <p className="text-stone text-xs mt-0.5">
                                /{c.slug} · {c.campaign_type === "exclusive_page" ? "Página exclusiva" : "Produtos em promoção"}
                              </p>
                              {c.end_at && (
                                <p className="text-stone text-xs mt-0.5">
                                  Até {new Date(c.end_at).toLocaleDateString("pt-BR")}
                                </p>
                              )}
                            </div>
                            <div className="flex gap-2 flex-shrink-0 flex-wrap justify-end">
                              <button
                                onClick={() => openCampaignProducts(c)}
                                className="px-3 py-1.5 text-xs bg-surface-03 text-parchment hover:bg-brand-mid rounded-lg transition-colors"
                              >
                                Produtos
                              </button>
                              <a
                                href={`/campanha/${c.slug}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-1.5 bg-surface-03 hover:bg-brand-mid text-parchment rounded-lg transition-colors"
                              >
                                <ExternalLink size={14} />
                              </a>
                              <button
                                onClick={() => openEditCampaign(c)}
                                className="p-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors"
                              >
                                <Edit2 size={14} />
                              </button>
                              <button
                                onClick={() => deleteCampaign(c.id)}
                                className="p-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {campaigns.length === 0 && (
                      <div className="text-center py-16">
                        <Sparkles size={48} className="text-slate-600 mx-auto mb-4" />
                        <p className="text-stone text-lg">Nenhuma campanha criada</p>
                        <button onClick={openCreateCampaign} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
                          <Plus size={16} /> Criar Primeira Campanha
                        </button>
                      </div>
                    )}

                    {/* ── Banners da Home (ex-Promoções) ── */}
                    <div className="mt-10 pt-8 border-t border-surface-03">
                      <div className="flex items-center justify-between mb-6">
                        <div>
                          <h3 className="text-cream font-bold text-lg flex items-center gap-2">
                            <Star size={18} className="text-gold" />
                            Banners da Home
                          </h3>
                          <p className="text-stone text-xs mt-1">Banners rotativos exibidos na página inicial da loja</p>
                        </div>
                        <button
                          onClick={openCreatePromo}
                          className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm"
                        >
                          <Plus size={16} />
                          Novo Banner
                        </button>
                      </div>

                      <div className="space-y-4">
                        {promotionsList.map((p) => (
                          <div key={p.id} className={`bg-surface-02 rounded-xl border border-surface-03 overflow-hidden ${!p.active ? "opacity-60" : ""}`}>
                            <div className="flex items-center gap-4 p-4">
                              <div className="w-14 h-14 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center overflow-hidden">
                                {p.icon && (p.icon.startsWith("data:") || p.icon.startsWith("http")) ? (
                                  <img src={p.icon} className="w-full h-full object-cover" alt={p.title} />
                                ) : (
                                  <span className="text-2xl">{p.icon || "⭐"}</span>
                                )}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <h3 className="text-cream font-bold text-sm">{p.title}</h3>
                                  <span className={`text-xs px-2 py-0.5 rounded-full border ${p.active ? "bg-green-500/20 text-green-400 border-green-500/30" : "bg-stone/20 text-stone border-stone/30"}`}>
                                    {p.active ? "Ativo" : "Inativo"}
                                  </span>
                                </div>
                                {p.subtitle && <p className="text-stone text-xs mt-0.5">{p.subtitle}</p>}
                                {p.validity_text && (
                                  <p className="text-gold/70 text-xs mt-0.5">📅 {p.validity_text}</p>
                                )}
                              </div>
                              <div className="flex gap-2 flex-shrink-0">
                                <button
                                  onClick={() => openEditPromo(p)}
                                  className="p-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors"
                                >
                                  <Edit2 size={14} />
                                </button>
                                <button
                                  onClick={() => deletePromo(p.id)}
                                  className="p-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>

                      {promotionsList.length === 0 && (
                        <div className="text-center py-8 bg-surface-02 rounded-xl border border-surface-03 border-dashed">
                          <Star size={32} className="text-stone mx-auto mb-3" />
                          <p className="text-stone text-sm">Nenhum banner criado</p>
                          <button onClick={openCreatePromo} className="mt-3 bg-gold hover:bg-gold/90 text-cream font-bold py-1.5 px-4 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
                            <Plus size={14} /> Criar Banner
                          </button>
                        </div>
                      )}
                    </div>
                  </>
                )}

                {/* ── TAB: KITS ──────────────────────────────────────────────── */}
                {activeTab === "kits" && (
                  <>
                    <div className="flex justify-end mb-6">
                      <button
                        onClick={openCreateKit}
                        className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm"
                      >
                        <Plus size={16} />
                        Novo Kit
                      </button>
                    </div>

                    <div className="space-y-4">
                      {kits.map((k) => (
                        <div key={k.id} className={`bg-surface-02 rounded-xl border border-surface-03 overflow-hidden ${!k.active ? "opacity-60" : ""}`}>
                          <div className="flex items-center gap-4 p-4">
                            <div className="w-12 h-12 rounded-xl bg-surface-03 flex-shrink-0 flex items-center justify-center text-2xl">
                              {k.icon}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <h3 className="text-cream font-bold text-sm">{k.name}</h3>
                                {!k.active && <span className="text-xs bg-surface-03 text-stone px-2 py-0.5 rounded-full">Inativo</span>}
                              </div>
                              <div className="flex gap-3 mt-0.5 text-xs text-stone">
                                <span>Original: R$ {k.price_original.toFixed(2)}</span>
                                <span className="text-gold">Promo: R$ {k.price_promotional.toFixed(2)}</span>
                                <span>{k.items.length} itens</span>
                              </div>
                            </div>
                            <div className="flex gap-2 flex-shrink-0">
                              <button
                                onClick={() => openKitItems(k)}
                                className="px-3 py-1.5 text-xs bg-surface-03 text-parchment hover:bg-brand-mid rounded-lg transition-colors"
                              >
                                Itens ({k.items.length})
                              </button>
                              <button
                                onClick={() => openEditKit(k)}
                                className="p-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors"
                              >
                                <Edit2 size={14} />
                              </button>
                              <button
                                onClick={() => deleteKit(k.id)}
                                className="p-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {kits.length === 0 && (
                      <div className="text-center py-16">
                        <Package size={48} className="text-slate-600 mx-auto mb-4" />
                        <p className="text-stone text-lg">Nenhum kit criado</p>
                        <button onClick={openCreateKit} className="mt-4 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-6 rounded-lg text-sm transition-colors inline-flex items-center gap-2">
                          <Plus size={16} /> Criar Primeiro Kit
                        </button>
                      </div>
                    )}
                  </>
                )}

                {/* ── TAB: USO CUPONS ────────────────────────────────────────── */}
                {activeTab === "uso_cupons" && (
                  <div>
                    <h3 className="text-cream font-bold text-lg mb-4">
                      Histórico de Uso de Cupons
                      <span className="text-stone text-sm font-normal ml-2">({usage.length} registros)</span>
                    </h3>
                    {usage.length === 0 ? (
                      <div className="text-center py-16">
                        <Tag size={48} className="text-slate-600 mx-auto mb-4" />
                        <p className="text-stone text-lg">Nenhum uso registrado</p>
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-surface-03">
                              <th className="text-left text-stone font-medium py-2 pr-4">Cupom</th>
                              <th className="text-left text-stone font-medium py-2 pr-4">Cliente ID</th>
                              <th className="text-left text-stone font-medium py-2 pr-4">Telefone</th>
                              <th className="text-left text-stone font-medium py-2 pr-4">Pedido</th>
                              <th className="text-left text-stone font-medium py-2">Data</th>
                            </tr>
                          </thead>
                          <tbody>
                            {usage.map((u) => (
                              <tr key={u.id} className="border-b border-surface-03/50 hover:bg-surface-02/50 transition-colors">
                                <td className="py-2 pr-4 text-gold font-mono text-xs">{getCouponCode(u.coupon_id)}</td>
                                <td className="py-2 pr-4 text-parchment text-xs">{u.customer_id ? u.customer_id.slice(0, 8) + "..." : "—"}</td>
                                <td className="py-2 pr-4 text-parchment text-xs">{u.phone ?? "—"}</td>
                                <td className="py-2 pr-4 text-parchment text-xs">{u.order_id ? u.order_id.slice(0, 12) + "..." : "—"}</td>
                                <td className="py-2 text-stone text-xs">
                                  {new Date(u.created_at).toLocaleString("pt-BR")}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Modal: Promotion Form ─────────────────────────────────────────────── */}
      {showPromoModal && (
        <Modal title={editingPromoId ? "Editar Promoção" : "Nova Promoção"} onClose={() => setShowPromoModal(false)}>
          <form onSubmit={handleSavePromo} className="space-y-4">
            <Inp label="Título *" value={promoForm.title} onChange={(e) => setPromoForm({ ...promoForm, title: e.target.value })} placeholder="Ex: Pizza do Mês" />

            <Inp label="Subtítulo" value={promoForm.subtitle} onChange={(e) => setPromoForm({ ...promoForm, subtitle: e.target.value })} placeholder="Slogan da promoção" />

            <ImageUpload
              value={promoForm.icon}
              onChange={(v) => setPromoForm({ ...promoForm, icon: v })}
              label="Imagem / Ícone"
              sizeGuide="Recomendado: 400×300px, máx. 500KB"
              hint="Imagem exibida no banner da promoção na loja."
              maxKB={500}
            />

            <Txt label="Descrição" value={promoForm.description} onChange={(e) => setPromoForm({ ...promoForm, description: e.target.value })} rows={2} placeholder="Detalhes da promoção" />

            <Inp label="Texto de validade" value={promoForm.validity_text} onChange={(e) => setPromoForm({ ...promoForm, validity_text: e.target.value })} placeholder="Ex: Válido até 30 de Junho" />

            <div className="grid grid-cols-2 gap-4">
              <Inp label="Válido de" type="datetime-local" value={promoForm.valid_from} onChange={(e) => setPromoForm({ ...promoForm, valid_from: e.target.value })} />
              <Inp label="Válido até" type="datetime-local" value={promoForm.valid_until} onChange={(e) => setPromoForm({ ...promoForm, valid_until: e.target.value })} />
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={promoForm.active} onChange={(e) => setPromoForm({ ...promoForm, active: e.target.checked })} className="w-4 h-4 accent-gold" />
              <span className="text-parchment text-sm">Ativa (visível na loja)</span>
            </label>

            <div className="flex gap-3 pt-2">
              <SaveBtn loading={promoSaving} />
              <button type="button" onClick={() => setShowPromoModal(false)} className="flex-1 bg-surface-03 hover:bg-slate-600 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
                Cancelar
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Modal: Coupon Form ────────────────────────────────────────────────── */}
      {showCouponModal && (
        <Modal title={editingCouponId ? "Editar Cupom" : "Novo Cupom"} onClose={() => setShowCouponModal(false)}>
          <form onSubmit={handleSaveCoupon} className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <Inp
                  label="Código *"
                  value={couponForm.code}
                  onChange={(e) => setCouponForm({ ...couponForm, code: e.target.value.toUpperCase() })}
                  placeholder="Ex: PIZZA10"
                  className="font-mono uppercase"
                />
              </div>
              <Inp label="Ícone / Emoji" value={couponForm.icon} onChange={(e) => setCouponForm({ ...couponForm, icon: e.target.value })} placeholder="🎟️" className="text-2xl" />
            </div>

            <Txt label="Descrição" value={couponForm.description} onChange={(e) => setCouponForm({ ...couponForm, description: e.target.value })} rows={2} placeholder="Descrição do cupom" />

            <div className="grid grid-cols-2 gap-4">
              <Sel label="Tipo de desconto" value={couponForm.coupon_type} onChange={(e) => setCouponForm({ ...couponForm, coupon_type: e.target.value as "percentage" | "fixed" })}>
                <option value="percentage">Percentual (%)</option>
                <option value="fixed">Valor Fixo (R$)</option>
              </Sel>
              <Inp
                label={couponForm.coupon_type === "percentage" ? "Desconto (%)" : "Desconto (R$)"}
                type="number" step="0.01" min="0"
                value={couponForm.discount_value}
                onChange={(e) => setCouponForm({ ...couponForm, discount_value: parseFloat(e.target.value) || 0 })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Inp label="Pedido mínimo (R$)" type="number" step="0.01" min="0" value={couponForm.min_order_value} onChange={(e) => setCouponForm({ ...couponForm, min_order_value: parseFloat(e.target.value) || 0 })} />
              <Inp label="Máx. de usos (deixe em branco = ilimitado)" type="number" min="1" value={couponForm.max_uses} onChange={(e) => setCouponForm({ ...couponForm, max_uses: e.target.value })} placeholder="Ilimitado" />
            </div>

            <Inp label="Data de validade" type="datetime-local" value={couponForm.expiry_date} onChange={(e) => setCouponForm({ ...couponForm, expiry_date: e.target.value })} />

            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={couponForm.active} onChange={(e) => setCouponForm({ ...couponForm, active: e.target.checked })} className="w-4 h-4 accent-gold" />
              <span className="text-parchment text-sm">Ativo</span>
            </label>

            <div className="flex gap-3 pt-2">
              <SaveBtn loading={couponSaving} />
              <button type="button" onClick={() => setShowCouponModal(false)} className="flex-1 bg-surface-03 hover:bg-slate-600 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
                Cancelar
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Modal: Campaign Form ──────────────────────────────────────────────── */}
      {showCampaignModal && (
        <Modal title={editingCampaignId ? "Editar Campanha" : "Nova Campanha"} onClose={() => setShowCampaignModal(false)}>
          <form onSubmit={handleSaveCampaign} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Inp label="Nome da Campanha *" value={campaignForm.name} onChange={(e) => setCampaignForm({ ...campaignForm, name: e.target.value })} placeholder="Ex: Promoção de Verão" />
              <Inp label="Slug / URL *" value={campaignForm.slug} onChange={(e) => setCampaignForm({ ...campaignForm, slug: e.target.value.toLowerCase().replace(/\s+/g, "-") })} placeholder="promocao-verao" />
            </div>

            <Txt label="Descrição" value={campaignForm.description} onChange={(e) => setCampaignForm({ ...campaignForm, description: e.target.value })} rows={2} placeholder="Descrição interna da campanha" />

            <div className="grid grid-cols-2 gap-4">
              <Sel label="Status" value={campaignForm.status} onChange={(e) => setCampaignForm({ ...campaignForm, status: e.target.value as CampaignStatus })}>
                <option value="draft">Rascunho</option>
                <option value="active">Ativa</option>
                <option value="paused">Pausada</option>
                <option value="ended">Encerrada</option>
              </Sel>
              <Sel label="Tipo" value={campaignForm.campaign_type} onChange={(e) => setCampaignForm({ ...campaignForm, campaign_type: e.target.value as CampaignType })}>
                <option value="products_promo">Produtos em Promoção</option>
                <option value="exclusive_page">Página Exclusiva</option>
              </Sel>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Inp label="Início" type="datetime-local" value={campaignForm.start_at} onChange={(e) => setCampaignForm({ ...campaignForm, start_at: e.target.value })} />
              <Inp label="Término" type="datetime-local" value={campaignForm.end_at} onChange={(e) => setCampaignForm({ ...campaignForm, end_at: e.target.value })} />
            </div>

            <label className="flex items-start gap-3 rounded-xl border border-surface-03 bg-surface-03/40 p-4 cursor-pointer">
              <input
                type="checkbox"
                checked={campaignForm.schedule_enabled}
                onChange={(e) => setCampaignForm({
                  ...campaignForm,
                  schedule_enabled: e.target.checked,
                  start_at: e.target.checked ? campaignForm.start_at : "",
                  end_at: e.target.checked ? campaignForm.end_at : "",
                })}
                className="w-4 h-4 mt-0.5 accent-gold"
              />
              <span>
                <span className="block text-parchment text-sm font-bold">Agendar campanha</span>
                <span className="block text-stone text-xs mt-0.5">Use os campos de inicio e termino acima para liberar a campanha automaticamente.</span>
              </span>
            </label>

            <ImageUpload
              value={campaignForm.banner}
              onChange={(v) => setCampaignForm({ ...campaignForm, banner: v })}
              label="Banner da Campanha"
              sizeGuide="Recomendado: 800×300px, máx. 500KB"
              hint="Imagem exibida na página pública da campanha."
              maxKB={500}
            />

            <div className="grid grid-cols-2 gap-4">
              <Inp label="Título de Exibição" value={campaignForm.display_title} onChange={(e) => setCampaignForm({ ...campaignForm, display_title: e.target.value })} placeholder="Título na página pública" />
              <Inp label="Subtítulo de Exibição" value={campaignForm.display_subtitle} onChange={(e) => setCampaignForm({ ...campaignForm, display_subtitle: e.target.value })} placeholder="Subtítulo" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Inp label="Ordem de Exibição" type="number" value={campaignForm.display_order} onChange={(e) => setCampaignForm({ ...campaignForm, display_order: parseInt(e.target.value) || 0 })} />
              <div className="flex items-end gap-3">
                <label className="flex items-center gap-2 cursor-pointer pb-2">
                  <input type="checkbox" checked={campaignForm.published} onChange={(e) => setCampaignForm({ ...campaignForm, published: e.target.checked })} className="w-4 h-4 accent-gold" />
                  <span className="text-parchment text-sm">Publicada (visível ao público)</span>
                </label>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <SaveBtn loading={campaignSaving} />
              <button type="button" onClick={() => setShowCampaignModal(false)} className="flex-1 bg-surface-03 hover:bg-slate-600 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
                Cancelar
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Modal: Campaign Products ──────────────────────────────────────────── */}
      {showCpModal && selectedCampaign && (
        <Modal title={`Produtos — ${selectedCampaign.name}`} onClose={() => setShowCpModal(false)}>
          <div className="space-y-4">
            <div className="bg-surface-03/50 rounded-xl p-4 space-y-3">
              <p className="text-parchment text-sm font-medium">Adicionar Produto</p>
              <div className="max-h-56 overflow-y-auto rounded-lg border border-surface-03 bg-surface-02/60 p-2 space-y-2">
                {products.map((p) => {
                  const checked = newCpProductIds.includes(p.id);
                  const alreadyLinked = cpList.some((cp) => cp.product_id === p.id);
                  return (
                    <label key={p.id} className={`flex items-center gap-3 rounded-lg px-3 py-2 cursor-pointer transition-colors ${checked ? "bg-gold/15 border border-gold/30" : "bg-surface-03/60 border border-transparent hover:border-gold/20"}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCampaignProductSelection(p.id)}
                        className="w-4 h-4 accent-gold"
                      />
                      <span className="text-lg leading-none">{p.icon}</span>
                      <span className="flex-1 min-w-0">
                        <span className="block text-cream text-sm font-medium truncate">{p.name}</span>
                        <span className="block text-stone text-xs">R$ {p.price.toFixed(2)}{alreadyLinked ? " · ja vinculado" : ""}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
              <p className="text-stone text-xs">
                {newCpProductIds.length} item(ns) selecionado(s). O preco/desconto abaixo sera aplicado a todos.
              </p>
              <div className="hidden">
                <Sel label="Produto" value={newCpProductIds[0] ?? ""} onChange={(e) => setNewCpProductIds(e.target.value ? [e.target.value] : [])}>
                  <option value="">Selecione...</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>{p.icon} {p.name} (R$ {p.price.toFixed(2)})</option>
                  ))}
                </Sel>
                <Inp label="Preço Promo (R$)" type="number" step="0.01" value={newCpPrice} onChange={(e) => setNewCpPrice(e.target.value)} placeholder="Deixe vazio para usar desconto" />
              </div>
              <Inp label="Preco Promo (R$)" type="number" step="0.01" value={newCpPrice} onChange={(e) => setNewCpPrice(e.target.value)} placeholder="Deixe vazio para usar desconto" />
              <div className="grid grid-cols-2 gap-3">
                <Sel label="Tipo de Desconto" value={newCpDiscType} onChange={(e) => setNewCpDiscType(e.target.value as CpDiscountType | "")}>
                  <option value="">Sem desconto extra</option>
                  <option value="percentage">Percentual (%)</option>
                  <option value="fixed">Valor Fixo (R$)</option>
                </Sel>
                <Inp label="Valor do Desconto" type="number" step="0.01" value={newCpDiscVal} onChange={(e) => setNewCpDiscVal(e.target.value)} placeholder="Ex: 10 (para 10% ou R$10)" disabled={!newCpDiscType} />
              </div>
              <button
                onClick={handleAddCampaignProduct}
                disabled={newCpProductIds.length === 0}
                className="w-full bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 rounded-lg text-sm transition-colors"
              >
                Adicionar selecionados
              </button>
            </div>

            <div className="space-y-2">
              {cpList.map((cp) => {
                const p = cp.product_id ? products.find((x) => x.id === cp.product_id) : null;
                return (
                  <div key={cp.id} className="flex items-center gap-3 bg-surface-02 rounded-lg p-3 border border-surface-03">
                    {p && <span className="text-xl">{p.icon}</span>}
                    <div className="flex-1 min-w-0">
                      <p className="text-cream text-sm font-medium">{p?.name ?? cp.product_id}</p>
                      <p className="text-stone text-xs">
                        {cp.promotional_price !== null ? `Promo: R$ ${cp.promotional_price?.toFixed(2)}` : ""}
                        {cp.discount_type && cp.discount_value ? ` · ${cp.discount_value}${cp.discount_type === "percentage" ? "%" : " R$"} off` : ""}
                      </p>
                    </div>
                    <button onClick={() => handleRemoveCampaignProduct(cp.id)} className="text-red-400 hover:text-red-300 transition-colors">
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}
              {cpList.length === 0 && (
                <p className="text-stone text-sm text-center py-4">Nenhum produto vinculado</p>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* ── Modal: Kit Form ────────────────────────────────────────────────────── */}
      {showKitModal && (
        <Modal title={editingKitId ? "Editar Kit" : "Novo Kit Promocional"} onClose={() => setShowKitModal(false)}>
          <form onSubmit={handleSaveKit} className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <div className="col-span-3">
                <Inp label="Nome do Kit *" value={kitForm.name} onChange={(e) => setKitForm({ ...kitForm, name: e.target.value })} placeholder="Ex: Kit Família Feliz" />
              </div>
              <Inp label="Ícone / Emoji" value={kitForm.icon} onChange={(e) => setKitForm({ ...kitForm, icon: e.target.value })} placeholder="🎁" className="text-2xl" />
            </div>

            <Txt label="Descrição" value={kitForm.description} onChange={(e) => setKitForm({ ...kitForm, description: e.target.value })} rows={2} placeholder="Descrição do kit" />

            <div className="grid grid-cols-2 gap-4">
              <Sel label="Tipo" value={kitForm.kit_type} onChange={(e) => setKitForm({ ...kitForm, kit_type: e.target.value as KitType })}>
                <option value="kit">Kit</option>
                <option value="product">Produto</option>
                <option value="item">Item Avulso</option>
              </Sel>
              <Inp label="Validade" type="datetime-local" value={kitForm.valid_until} onChange={(e) => setKitForm({ ...kitForm, valid_until: e.target.value })} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Inp label="Preço Original (R$)" type="number" step="0.01" value={kitForm.price_original} onChange={(e) => setKitForm({ ...kitForm, price_original: parseFloat(e.target.value) || 0 })} />
              <Inp label="Preço Promocional (R$)" type="number" step="0.01" value={kitForm.price_promotional} onChange={(e) => setKitForm({ ...kitForm, price_promotional: parseFloat(e.target.value) || 0 })} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Sel label="Tipo de Desconto" value={kitForm.discount_type} onChange={(e) => setKitForm({ ...kitForm, discount_type: e.target.value as CpDiscountType | "" })}>
                <option value="">Sem desconto calculado</option>
                <option value="percentage">Percentual (%)</option>
                <option value="fixed">Valor Fixo (R$)</option>
              </Sel>
              <Inp label="Valor do Desconto" type="number" step="0.01" value={kitForm.discount_value} onChange={(e) => setKitForm({ ...kitForm, discount_value: parseFloat(e.target.value) || 0 })} disabled={!kitForm.discount_type} />
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={kitForm.active} onChange={(e) => setKitForm({ ...kitForm, active: e.target.checked })} className="w-4 h-4 accent-gold" />
              <span className="text-parchment text-sm">Ativo</span>
            </label>

            <div className="flex gap-3 pt-2">
              <SaveBtn loading={kitSaving} />
              <button type="button" onClick={() => setShowKitModal(false)} className="flex-1 bg-surface-03 hover:bg-slate-600 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
                Cancelar
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Modal: Kit Items ────────────────────────────────────────────────────── */}
      {showKitItemsModal && selectedKit && (
        <Modal title={`Itens — ${selectedKit.name}`} onClose={() => setShowKitItemsModal(false)}>
          <div className="space-y-4">
            <div className="bg-surface-03/50 rounded-xl p-4 space-y-3">
              <p className="text-parchment text-sm font-medium">Adicionar Item ao Kit</p>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Sel label="Produto" value={newKitItemProductId} onChange={(e) => setNewKitItemProductId(e.target.value)}>
                    <option value="">Selecione...</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>{p.icon} {p.name}</option>
                    ))}
                  </Sel>
                </div>
                <Inp label="Quantidade" type="number" min={1} value={newKitItemQty} onChange={(e) => setNewKitItemQty(parseInt(e.target.value) || 1)} />
              </div>
              <button
                onClick={handleAddKitItem}
                disabled={!newKitItemProductId}
                className="w-full bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 rounded-lg text-sm transition-colors"
              >
                Adicionar ao Kit
              </button>
            </div>

            <div className="space-y-2">
              {selectedKit.items.map((item) => (
                <div key={item.id} className="flex items-center gap-3 bg-surface-02 rounded-lg p-3 border border-surface-03">
                  <div className="flex-1">
                    <p className="text-cream text-sm">{getProductName(item.product_id)}</p>
                    <p className="text-stone text-xs">Qtd: {item.quantity}</p>
                  </div>
                  <button onClick={() => handleRemoveKitItem(item.id)} className="text-red-400 hover:text-red-300 transition-colors">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              {selectedKit.items.length === 0 && (
                <p className="text-stone text-sm text-center py-4">Nenhum item no kit</p>
              )}
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
