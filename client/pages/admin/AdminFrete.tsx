import { useState, useEffect, useCallback } from "react";
import AdminSidebar from "@/components/AdminSidebar";
import { apiRequest } from "@/lib/api";
import {
  Truck, Settings, MapPin, Hash, Ruler, DollarSign, Sparkles, Zap,
  Plus, Pencil, Trash2, Check, X, ToggleLeft, ToggleRight, AlertCircle,
  Package, Clock, ChevronDown, ChevronUp,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ShippingConfig {
  delivery_enabled: boolean; pickup_enabled: boolean; pickup_message: string;
  min_order_value: number; default_estimated_time: number; max_delivery_distance: number;
  default_base_fee: number; unavailable_message: string;
  store_lat: number | null; store_lng: number | null;
}

interface FreightTypeConfig {
  id: string; freight_type: string; active: boolean; priority: number;
  fixed_value: number; free_above_value: number;
  scheduled_surcharge: number; scheduled_surcharge_type: string;
}

interface Neighborhood {
  id: string; name: string; city: string; shipping_value: number;
  is_free: boolean; min_order_value: number; estimated_time_min: number;
  notes: string; active: boolean; priority: number;
}

interface CepRange {
  id: string; name: string; cep_start: string; cep_end: string;
  shipping_value: number; min_order_value: number;
  estimated_time_min: number; active: boolean; priority: number;
}

interface DistanceRule {
  id: string; name: string; km_min: number; km_max: number;
  base_fee: number; fee_per_km: number; min_fee: number; max_fee: number;
  estimated_time_min: number; active: boolean; priority: number;
}

interface OrderValueTier {
  id: string; name: string; order_value_min: number; order_value_max: number | null;
  shipping_value: number; is_free: boolean; active: boolean; priority: number;
}

interface ShippingPromotion {
  id: string; name: string; promo_type: string; min_order_value: number;
  shipping_value: number; neighborhood_ids: string;
  valid_from: string | null; valid_until: string | null;
  active: boolean; priority: number;
}

interface ExtraRule {
  id: string; rule_type: string; name: string; value: number; value_type: string;
  condition: string; message: string; active: boolean; priority: number;
  time_start: string | null; time_end: string | null;
}

const api = apiRequest;

// ─── Helper components ────────────────────────────────────────────────────────

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!value)} className="flex-shrink-0">
      {value
        ? <ToggleRight size={28} className="text-gold" />
        : <ToggleLeft size={28} className="text-stone" />}
    </button>
  );
}

function Badge({ active }: { active: boolean }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${active ? "bg-gold/20 text-gold-light" : "bg-surface-03 text-stone"}`}>
      {active ? "Ativo" : "Inativo"}
    </span>
  );
}

function Input({ label, value, onChange, type = "text", placeholder = "", step }: {
  label: string; value: string | number; onChange: (v: string) => void;
  type?: string; placeholder?: string; step?: string;
}) {
  return (
    <div>
      <label className="block text-parchment text-xs mb-1">{label}</label>
      <input
        type={type} step={step} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-surface-03 border border-surface-03 focus:border-gold text-cream placeholder-stone/50 rounded-lg px-3 py-2 text-sm outline-none transition-colors"
      />
    </div>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="block text-parchment text-xs mb-1">{label}</label>
      <select
        value={value} onChange={(e) => onChange(e.target.value)}
        className="w-full bg-surface-03 border border-surface-03 focus:border-gold text-cream rounded-lg px-3 py-2 text-sm outline-none"
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function Textarea({ label, value, onChange, rows = 2 }: {
  label: string; value: string; onChange: (v: string) => void; rows?: number;
}) {
  return (
    <div>
      <label className="block text-parchment text-xs mb-1">{label}</label>
      <textarea
        value={value} onChange={(e) => onChange(e.target.value)} rows={rows}
        className="w-full bg-surface-03 border border-surface-03 focus:border-gold text-cream placeholder-stone/50 rounded-lg px-3 py-2 text-sm outline-none resize-none transition-colors"
      />
    </div>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-cream font-bold text-lg">{title}</h3>
          <button onClick={onClose} className="text-stone hover:text-cream transition-colors"><X size={20} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function SaveBtn({ onClick, saving }: { onClick: () => void; saving: boolean }) {
  return (
    <button onClick={onClick} disabled={saving}
      className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold rounded-lg text-sm transition-colors">
      {saving ? <span className="animate-spin">⏳</span> : <Check size={16} />}
      {saving ? "Salvando..." : "Salvar"}
    </button>
  );
}

const TABS = [
  { id: "overview", label: "Visão Geral", icon: Truck },
  { id: "config", label: "Configurações", icon: Settings },
  { id: "types", label: "Tipos de Frete", icon: Package },
  { id: "neighborhoods", label: "Bairros", icon: MapPin },
  { id: "cep", label: "Faixas de CEP", icon: Hash },
  { id: "distance", label: "Por Distância", icon: Ruler },
  { id: "value", label: "Por Valor", icon: DollarSign },
  { id: "promotions", label: "Promoções", icon: Sparkles },
  { id: "extras", label: "Regras Extras", icon: Zap },
];

const FREIGHT_TYPE_LABELS: Record<string, string> = {
  fixed: "Frete Fixo", by_neighborhood: "Por Bairro", by_cep_range: "Por CEP",
  by_distance: "Por Distância", by_order_value: "Por Valor do Pedido",
  free: "Frete Grátis", pickup: "Retirada no Local", scheduled: "Entrega Agendada",
};

const PROMO_TYPE_OPTIONS = [
  { value: "free_above_value", label: "Grátis acima de valor" },
  { value: "promotional_period", label: "Frete promocional por período" },
  { value: "free_by_neighborhood", label: "Grátis por bairro" },
  { value: "free_campaign", label: "Campanha de frete grátis" },
];

const EXTRA_TYPE_OPTIONS = [
  { value: "time_surcharge", label: "Adicional por horário" },
  { value: "demand_surcharge", label: "Adicional por alta demanda" },
  { value: "area_surcharge", label: "Adicional por área" },
  { value: "scheduled_surcharge", label: "Adicional entrega agendada" },
  { value: "region_block", label: "Bloquear região" },
];

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AdminFrete() {
  const [tab, setTab] = useState("overview");
  const [toast, setToast] = useState("");

  const [config, setConfig] = useState<ShippingConfig | null>(null);
  const [typeConfigs, setTypeConfigs] = useState<FreightTypeConfig[]>([]);
  const [neighborhoods, setNeighborhoods] = useState<Neighborhood[]>([]);
  const [cepRanges, setCepRanges] = useState<CepRange[]>([]);
  const [distanceRules, setDistanceRules] = useState<DistanceRule[]>([]);
  const [orderValueTiers, setOrderValueTiers] = useState<OrderValueTier[]>([]);
  const [promotions, setPromotions] = useState<ShippingPromotion[]>([]);
  const [extraRules, setExtraRules] = useState<ExtraRule[]>([]);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  const loadAll = useCallback(async () => {
    try {
      const [cfg, types, nbhd, cep, dist, tiers, promos, extras] = await Promise.all([
        api<ShippingConfig>("GET", "/shipping/config"),
        api<FreightTypeConfig[]>("GET", "/shipping/types"),
        api<Neighborhood[]>("GET", "/shipping/neighborhoods"),
        api<CepRange[]>("GET", "/shipping/cep-ranges"),
        api<DistanceRule[]>("GET", "/shipping/distance-rules"),
        api<OrderValueTier[]>("GET", "/shipping/order-value-tiers"),
        api<ShippingPromotion[]>("GET", "/shipping/promotions"),
        api<ExtraRule[]>("GET", "/shipping/extra-rules"),
      ]);
      setConfig(cfg); setTypeConfigs(types); setNeighborhoods(nbhd);
      setCepRanges(cep); setDistanceRules(dist); setOrderValueTiers(tiers);
      setPromotions(promos); setExtraRules(extras);
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-surface-02 border-b border-surface-03 px-6 py-4 flex items-center gap-3">
          <Truck size={24} className="text-gold" />
          <h1 className="text-cream font-bold text-xl">Gestão de Frete</h1>
        </div>

        {/* Tab bar */}
        <div className="bg-surface-02 border-b border-surface-03 px-6 flex gap-1 overflow-x-auto">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === id ? "border-gold text-gold-light" : "border-transparent text-stone hover:text-parchment"
              }`}>
              <Icon size={16} />{label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {tab === "overview" && <TabOverview typeConfigs={typeConfigs} neighborhoods={neighborhoods} cepRanges={cepRanges} extraRules={extraRules} promotions={promotions} config={config} />}
          {tab === "config" && <TabConfig config={config} setConfig={setConfig} showToast={showToast} />}
          {tab === "types" && <TabTypes typeConfigs={typeConfigs} setTypeConfigs={setTypeConfigs} showToast={showToast} />}
          {tab === "neighborhoods" && <TabNeighborhoods neighborhoods={neighborhoods} setNeighborhoods={setNeighborhoods} showToast={showToast} />}
          {tab === "cep" && <TabCepRanges cepRanges={cepRanges} setCepRanges={setCepRanges} showToast={showToast} />}
          {tab === "distance" && <TabDistanceRules distanceRules={distanceRules} setDistanceRules={setDistanceRules} showToast={showToast} />}
          {tab === "value" && <TabOrderValueTiers tiers={orderValueTiers} setTiers={setOrderValueTiers} showToast={showToast} />}
          {tab === "promotions" && <TabPromotions promotions={promotions} setPromotions={setPromotions} showToast={showToast} />}
          {tab === "extras" && <TabExtras extraRules={extraRules} setExtraRules={setExtraRules} showToast={showToast} />}
        </div>
      </div>

      {toast && (
        <div className="fixed bottom-6 right-6 bg-surface-02 border border-gold/40 text-cream px-5 py-3 rounded-xl shadow-xl z-50 flex items-center gap-2">
          <Check size={16} className="text-gold" />{toast}
        </div>
      )}
    </div>
  );
}

// ─── Tab: Overview ────────────────────────────────────────────────────────────

function TabOverview({ typeConfigs, neighborhoods, cepRanges, extraRules, promotions, config }: {
  typeConfigs: FreightTypeConfig[]; neighborhoods: Neighborhood[];
  cepRanges: CepRange[]; extraRules: ExtraRule[];
  promotions: ShippingPromotion[]; config: ShippingConfig | null;
}) {
  const active = typeConfigs.filter(t => t.active).length;
  const stats = [
    { label: "Tipos ativos", value: active, icon: Package, color: "text-gold" },
    { label: "Bairros cadastrados", value: neighborhoods.length, icon: MapPin, color: "text-blue-400" },
    { label: "Faixas de CEP", value: cepRanges.length, icon: Hash, color: "text-purple-400" },
    { label: "Promoções ativas", value: promotions.filter(p => p.active).length, icon: Sparkles, color: "text-green-400" },
    { label: "Regras extras", value: extraRules.filter(r => r.active).length, icon: Zap, color: "text-orange-400" },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-surface-02 border border-surface-03 rounded-xl p-4">
            <Icon size={20} className={`${color} mb-2`} />
            <p className="text-cream font-bold text-2xl">{value}</p>
            <p className="text-stone text-xs mt-1">{label}</p>
          </div>
        ))}
      </div>

      {config && (
        <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-3">
          <h2 className="text-cream font-bold">Status atual</h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${config.delivery_enabled ? "bg-green-400" : "bg-red-400"}`} />
              <span className="text-parchment text-sm">Delivery {config.delivery_enabled ? "habilitado" : "desabilitado"}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${config.pickup_enabled ? "bg-green-400" : "bg-red-400"}`} />
              <span className="text-parchment text-sm">Retirada {config.pickup_enabled ? "habilitada" : "desabilitada"}</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock size={14} className="text-stone" />
              <span className="text-parchment text-sm">Tempo padrão: {config.default_estimated_time} min</span>
            </div>
            <div className="flex items-center gap-2">
              <Ruler size={14} className="text-stone" />
              <span className="text-parchment text-sm">Distância máx: {config.max_delivery_distance} km</span>
            </div>
          </div>
        </div>
      )}

      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5">
        <h2 className="text-cream font-bold mb-3">Tipos de frete configurados</h2>
        <div className="space-y-2">
          {typeConfigs.sort((a, b) => b.priority - a.priority).map(tc => (
            <div key={tc.id} className="flex items-center justify-between py-2 border-b border-surface-03 last:border-0">
              <span className="text-parchment text-sm">{FREIGHT_TYPE_LABELS[tc.freight_type] ?? tc.freight_type}</span>
              <div className="flex items-center gap-3">
                <span className="text-stone text-xs">Prioridade: {tc.priority}</span>
                <Badge active={tc.active} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Tab: Config ──────────────────────────────────────────────────────────────

function TabConfig({ config, setConfig, showToast }: {
  config: ShippingConfig | null;
  setConfig: (c: ShippingConfig) => void;
  showToast: (m: string) => void;
}) {
  const [form, setForm] = useState<ShippingConfig | null>(config);
  const [saving, setSaving] = useState(false);

  useEffect(() => { setForm(config); }, [config]);

  if (!form) return <p className="text-stone text-sm">Carregando...</p>;

  const set = (k: keyof ShippingConfig, v: unknown) => setForm(prev => ({ ...prev!, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api<ShippingConfig>("PUT", "/shipping/config", form);
      setConfig(updated); showToast("Configurações salvas!");
    } catch (e: unknown) {
      showToast(`Erro: ${(e as Error).message}`);
    } finally { setSaving(false); }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-4">
        <h2 className="text-cream font-bold">Serviços</h2>
        <div className="flex items-center justify-between py-2 border-b border-surface-03">
          <div>
            <p className="text-cream text-sm font-medium">Delivery habilitado</p>
            <p className="text-stone text-xs">Permitir pedidos com entrega</p>
          </div>
          <Toggle value={form.delivery_enabled} onChange={v => set("delivery_enabled", v)} />
        </div>
        <div className="flex items-center justify-between py-2">
          <div>
            <p className="text-cream text-sm font-medium">Retirada no local</p>
            <p className="text-stone text-xs">Cliente retira na loja sem frete</p>
          </div>
          <Toggle value={form.pickup_enabled} onChange={v => set("pickup_enabled", v)} />
        </div>
        {form.pickup_enabled && (
          <Input label="Mensagem de retirada" value={form.pickup_message}
            onChange={v => set("pickup_message", v)} />
        )}
      </div>

      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-4">
        <h2 className="text-cream font-bold">Valores padrão</h2>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Pedido mínimo (R$)" type="number" step="0.01"
            value={form.min_order_value} onChange={v => set("min_order_value", parseFloat(v) || 0)} />
          <Input label="Taxa padrão (R$)" type="number" step="0.01"
            value={form.default_base_fee} onChange={v => set("default_base_fee", parseFloat(v) || 0)} />
          <Input label="Tempo estimado padrão (min)" type="number"
            value={form.default_estimated_time} onChange={v => set("default_estimated_time", parseInt(v) || 45)} />
          <Input label="Distância máxima (km)" type="number" step="0.1"
            value={form.max_delivery_distance} onChange={v => set("max_delivery_distance", parseFloat(v) || 20)} />
        </div>
      </div>

      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-4">
        <h2 className="text-cream font-bold">Mensagens</h2>
        <Textarea label="Mensagem quando região não atendida"
          value={form.unavailable_message} onChange={v => set("unavailable_message", v)} />
      </div>

      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-4">
        <h2 className="text-cream font-bold">Coordenadas da loja (para cálculo por distância)</h2>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Latitude" type="number" step="0.000001"
            value={form.store_lat ?? ""} onChange={v => set("store_lat", v ? parseFloat(v) : null)} />
          <Input label="Longitude" type="number" step="0.000001"
            value={form.store_lng ?? ""} onChange={v => set("store_lng", v ? parseFloat(v) : null)} />
        </div>
      </div>

      <div className="flex justify-end">
        <SaveBtn onClick={save} saving={saving} />
      </div>
    </div>
  );
}

// ─── Tab: Types ───────────────────────────────────────────────────────────────

function TabTypes({ typeConfigs, setTypeConfigs, showToast }: {
  typeConfigs: FreightTypeConfig[];
  setTypeConfigs: (t: FreightTypeConfig[]) => void;
  showToast: (m: string) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Partial<FreightTypeConfig>>>({});

  const setDraft = (ft: string, k: string, v: unknown) =>
    setDrafts(prev => ({ ...prev, [ft]: { ...prev[ft], [k]: v } }));

  const getDraft = (tc: FreightTypeConfig) => ({ ...tc, ...drafts[tc.freight_type] });

  const save = async (tc: FreightTypeConfig) => {
    const d = getDraft(tc);
    setSaving(tc.freight_type);
    try {
      const updated = await api<FreightTypeConfig>("PUT", `/shipping/types/${tc.freight_type}`, {
        active: d.active, priority: d.priority,
        fixed_value: d.fixed_value, free_above_value: d.free_above_value,
        scheduled_surcharge: d.scheduled_surcharge,
        scheduled_surcharge_type: d.scheduled_surcharge_type,
      });
      setTypeConfigs(typeConfigs.map(x => x.freight_type === tc.freight_type ? updated : x));
      setDrafts(prev => { const n = { ...prev }; delete n[tc.freight_type]; return n; });
      showToast("Tipo de frete atualizado!");
    } catch (e: unknown) {
      showToast(`Erro: ${(e as Error).message}`);
    } finally { setSaving(null); }
  };

  const sorted = [...typeConfigs].sort((a, b) => b.priority - a.priority);

  return (
    <div className="space-y-3 max-w-2xl">
      <p className="text-stone text-sm mb-4">Configure quais tipos de frete estão ativos e defina a prioridade de avaliação (maior prioridade = avaliado primeiro).</p>
      {sorted.map(tc => {
        const d = getDraft(tc);
        const isOpen = expanded === tc.freight_type;
        return (
          <div key={tc.id} className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3">
              <Toggle value={d.active ?? false} onChange={v => setDraft(tc.freight_type, "active", v)} />
              <span className="text-cream font-medium flex-1">{FREIGHT_TYPE_LABELS[tc.freight_type] ?? tc.freight_type}</span>
              <Badge active={d.active ?? false} />
              <button onClick={() => setExpanded(isOpen ? null : tc.freight_type)}
                className="text-stone hover:text-cream transition-colors">
                {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
            </div>
            {isOpen && (
              <div className="border-t border-surface-03 px-4 pb-4 pt-3 space-y-3">
                <Input label="Prioridade (maior = primeiro)" type="number"
                  value={d.priority ?? 0} onChange={v => setDraft(tc.freight_type, "priority", parseInt(v) || 0)} />
                {tc.freight_type === "fixed" && (
                  <Input label="Valor fixo (R$)" type="number" step="0.01"
                    value={d.fixed_value ?? 0} onChange={v => setDraft(tc.freight_type, "fixed_value", parseFloat(v) || 0)} />
                )}
                {tc.freight_type === "free" && (
                  <Input label="Frete grátis acima de (R$) — 0 = sempre grátis" type="number" step="0.01"
                    value={d.free_above_value ?? 0} onChange={v => setDraft(tc.freight_type, "free_above_value", parseFloat(v) || 0)} />
                )}
                {tc.freight_type === "scheduled" && (
                  <div className="grid grid-cols-2 gap-3">
                    <Input label="Acréscimo para agendado" type="number" step="0.01"
                      value={d.scheduled_surcharge ?? 0} onChange={v => setDraft(tc.freight_type, "scheduled_surcharge", parseFloat(v) || 0)} />
                    <Select label="Tipo de acréscimo"
                      value={d.scheduled_surcharge_type ?? "fixed"}
                      onChange={v => setDraft(tc.freight_type, "scheduled_surcharge_type", v)}
                      options={[{ value: "fixed", label: "Valor fixo (R$)" }, { value: "percentage", label: "Percentual (%)" }]} />
                  </div>
                )}
                <div className="flex justify-end pt-1">
                  <SaveBtn onClick={() => save(tc)} saving={saving === tc.freight_type} />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Tab: Neighborhoods ───────────────────────────────────────────────────────

function TabNeighborhoods({ neighborhoods, setNeighborhoods, showToast }: {
  neighborhoods: Neighborhood[];
  setNeighborhoods: (n: Neighborhood[]) => void;
  showToast: (m: string) => void;
}) {
  const empty: Omit<Neighborhood, "id"> = {
    name: "", city: "", shipping_value: 0, is_free: false,
    min_order_value: 0, estimated_time_min: 45, notes: "", active: true, priority: 0,
  };
  const [modal, setModal] = useState<{ mode: "add" | "edit"; data: Partial<Neighborhood> } | null>(null);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = neighborhoods.filter(n =>
    n.name.toLowerCase().includes(search.toLowerCase()) ||
    n.city.toLowerCase().includes(search.toLowerCase())
  );

  const set = (k: string, v: unknown) => setModal(m => m ? { ...m, data: { ...m.data, [k]: v } } : null);

  const save = async () => {
    if (!modal) return;
    setSaving(true);
    try {
      if (modal.mode === "add") {
        const n = await api<Neighborhood>("POST", "/shipping/neighborhoods", modal.data);
        setNeighborhoods([...neighborhoods, n]);
      } else {
        const n = await api<Neighborhood>("PUT", `/shipping/neighborhoods/${modal.data.id}`, modal.data);
        setNeighborhoods(neighborhoods.map(x => x.id === n.id ? n : x));
      }
      setModal(null); showToast("Bairro salvo!");
    } catch (e: unknown) {
      showToast(`Erro: ${(e as Error).message}`);
    } finally { setSaving(false); }
  };

  const remove = async (id: string) => {
    if (!confirm("Remover este bairro?")) return;
    try {
      await api("DELETE", `/shipping/neighborhoods/${id}`);
      setNeighborhoods(neighborhoods.filter(n => n.id !== id));
      showToast("Bairro removido.");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const toggle = async (n: Neighborhood) => {
    try {
      const updated = await api<Neighborhood>("PUT", `/shipping/neighborhoods/${n.id}`, { active: !n.active });
      setNeighborhoods(neighborhoods.map(x => x.id === n.id ? updated : x));
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <input placeholder="Buscar bairro ou cidade..." value={search} onChange={e => setSearch(e.target.value)}
          className="flex-1 bg-surface-02 border border-surface-03 focus:border-gold text-cream placeholder-stone/50 rounded-lg px-3 py-2 text-sm outline-none" />
        <button onClick={() => setModal({ mode: "add", data: { ...empty } })}
          className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 text-cream font-bold rounded-lg text-sm">
          <Plus size={16} /> Novo Bairro
        </button>
      </div>

      <div className="space-y-2">
        {filtered.length === 0 && <p className="text-stone text-sm text-center py-8">Nenhum bairro cadastrado.</p>}
        {filtered.map(n => (
          <div key={n.id} className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 flex items-center gap-3">
            <Toggle value={n.active} onChange={() => toggle(n)} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-cream font-medium text-sm">{n.name}</p>
                {n.city && <span className="text-stone text-xs">— {n.city}</span>}
                <Badge active={n.active} />
              </div>
              <div className="flex gap-3 mt-0.5 flex-wrap">
                <span className="text-stone text-xs">{n.is_free ? "Frete Grátis" : `R$ ${n.shipping_value.toFixed(2)}`}</span>
                {n.min_order_value > 0 && <span className="text-stone text-xs">Mín: R$ {n.min_order_value.toFixed(2)}</span>}
                <span className="text-stone text-xs">⏱ {n.estimated_time_min} min</span>
                <span className="text-stone text-xs">Prioridade: {n.priority}</span>
              </div>
            </div>
            <button onClick={() => setModal({ mode: "edit", data: { ...n } })} className="text-stone hover:text-gold transition-colors p-1"><Pencil size={16} /></button>
            <button onClick={() => remove(n.id)} className="text-stone hover:text-red-400 transition-colors p-1"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>

      {modal && (
        <Modal title={modal.mode === "add" ? "Novo Bairro" : "Editar Bairro"} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Input label="Nome do bairro *" value={modal.data.name ?? ""} onChange={v => set("name", v)} />
              <Input label="Cidade" value={modal.data.city ?? ""} onChange={v => set("city", v)} />
            </div>
            <div className="flex items-center gap-3 py-1">
              <Toggle value={modal.data.is_free ?? false} onChange={v => set("is_free", v)} />
              <span className="text-parchment text-sm">Frete grátis neste bairro</span>
            </div>
            {!modal.data.is_free && (
              <Input label="Valor do frete (R$)" type="number" step="0.01"
                value={modal.data.shipping_value ?? 0} onChange={v => set("shipping_value", parseFloat(v) || 0)} />
            )}
            <div className="grid grid-cols-2 gap-3">
              <Input label="Pedido mínimo (R$)" type="number" step="0.01"
                value={modal.data.min_order_value ?? 0} onChange={v => set("min_order_value", parseFloat(v) || 0)} />
              <Input label="Tempo estimado (min)" type="number"
                value={modal.data.estimated_time_min ?? 45} onChange={v => set("estimated_time_min", parseInt(v) || 45)} />
            </div>
            <Input label="Prioridade" type="number"
              value={modal.data.priority ?? 0} onChange={v => set("priority", parseInt(v) || 0)} />
            <Textarea label="Observações" value={modal.data.notes ?? ""} onChange={v => set("notes", v)} />
            <div className="flex items-center gap-3 py-1">
              <Toggle value={modal.data.active ?? true} onChange={v => set("active", v)} />
              <span className="text-parchment text-sm">Bairro ativo</span>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-surface-03 text-stone rounded-lg text-sm hover:border-slate-500">Cancelar</button>
              <SaveBtn onClick={save} saving={saving} />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── Tab: CEP Ranges ──────────────────────────────────────────────────────────

function TabCepRanges({ cepRanges, setCepRanges, showToast }: {
  cepRanges: CepRange[]; setCepRanges: (r: CepRange[]) => void; showToast: (m: string) => void;
}) {
  const empty: Omit<CepRange, "id"> = {
    name: "", cep_start: "", cep_end: "", shipping_value: 0,
    min_order_value: 0, estimated_time_min: 45, active: true, priority: 0,
  };
  const [modal, setModal] = useState<{ mode: "add" | "edit"; data: Partial<CepRange> } | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: string, v: unknown) => setModal(m => m ? { ...m, data: { ...m.data, [k]: v } } : null);

  const save = async () => {
    if (!modal) return;
    setSaving(true);
    try {
      if (modal.mode === "add") {
        const r = await api<CepRange>("POST", "/shipping/cep-ranges", modal.data);
        setCepRanges([...cepRanges, r]);
      } else {
        const r = await api<CepRange>("PUT", `/shipping/cep-ranges/${modal.data.id}`, modal.data);
        setCepRanges(cepRanges.map(x => x.id === r.id ? r : x));
      }
      setModal(null); showToast("Faixa de CEP salva!");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
    finally { setSaving(false); }
  };

  const remove = async (id: string) => {
    if (!confirm("Remover faixa de CEP?")) return;
    try {
      await api("DELETE", `/shipping/cep-ranges/${id}`);
      setCepRanges(cepRanges.filter(r => r.id !== id)); showToast("Removida.");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const toggle = async (r: CepRange) => {
    try {
      const u = await api<CepRange>("PUT", `/shipping/cep-ranges/${r.id}`, { active: !r.active });
      setCepRanges(cepRanges.map(x => x.id === r.id ? u : x));
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setModal({ mode: "add", data: { ...empty } })}
          className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 text-cream font-bold rounded-lg text-sm">
          <Plus size={16} /> Nova Faixa de CEP
        </button>
      </div>
      <div className="space-y-2">
        {cepRanges.length === 0 && <p className="text-stone text-sm text-center py-8">Nenhuma faixa de CEP cadastrada.</p>}
        {cepRanges.map(r => (
          <div key={r.id} className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 flex items-center gap-3">
            <Toggle value={r.active} onChange={() => toggle(r)} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-cream font-medium text-sm">{r.name || `CEP ${r.cep_start} – ${r.cep_end}`}</p>
                <Badge active={r.active} />
              </div>
              <div className="flex gap-3 mt-0.5">
                <span className="text-stone text-xs">{r.cep_start} – {r.cep_end}</span>
                <span className="text-stone text-xs">R$ {r.shipping_value.toFixed(2)}</span>
                {r.min_order_value > 0 && <span className="text-stone text-xs">Mín: R$ {r.min_order_value.toFixed(2)}</span>}
                <span className="text-stone text-xs">⏱ {r.estimated_time_min} min</span>
              </div>
            </div>
            <button onClick={() => setModal({ mode: "edit", data: { ...r } })} className="text-stone hover:text-gold p-1"><Pencil size={16} /></button>
            <button onClick={() => remove(r.id)} className="text-stone hover:text-red-400 p-1"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      {modal && (
        <Modal title={modal.mode === "add" ? "Nova Faixa de CEP" : "Editar Faixa de CEP"} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Input label="Nome (opcional)" value={modal.data.name ?? ""} onChange={v => set("name", v)} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="CEP inicial *" value={modal.data.cep_start ?? ""} onChange={v => set("cep_start", v)} placeholder="00000-000" />
              <Input label="CEP final *" value={modal.data.cep_end ?? ""} onChange={v => set("cep_end", v)} placeholder="99999-999" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Valor do frete (R$)" type="number" step="0.01"
                value={modal.data.shipping_value ?? 0} onChange={v => set("shipping_value", parseFloat(v) || 0)} />
              <Input label="Pedido mínimo (R$)" type="number" step="0.01"
                value={modal.data.min_order_value ?? 0} onChange={v => set("min_order_value", parseFloat(v) || 0)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Tempo estimado (min)" type="number"
                value={modal.data.estimated_time_min ?? 45} onChange={v => set("estimated_time_min", parseInt(v) || 45)} />
              <Input label="Prioridade" type="number"
                value={modal.data.priority ?? 0} onChange={v => set("priority", parseInt(v) || 0)} />
            </div>
            <div className="flex items-center gap-3"><Toggle value={modal.data.active ?? true} onChange={v => set("active", v)} /><span className="text-parchment text-sm">Ativo</span></div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-surface-03 text-stone rounded-lg text-sm">Cancelar</button>
              <SaveBtn onClick={save} saving={saving} />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── Tab: Distance Rules ──────────────────────────────────────────────────────

function TabDistanceRules({ distanceRules, setDistanceRules, showToast }: {
  distanceRules: DistanceRule[]; setDistanceRules: (r: DistanceRule[]) => void; showToast: (m: string) => void;
}) {
  const empty: Omit<DistanceRule, "id"> = {
    name: "", km_min: 0, km_max: 5, base_fee: 0, fee_per_km: 0,
    min_fee: 0, max_fee: 999, estimated_time_min: 45, active: true, priority: 0,
  };
  const [modal, setModal] = useState<{ mode: "add" | "edit"; data: Partial<DistanceRule> } | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: string, v: unknown) => setModal(m => m ? { ...m, data: { ...m.data, [k]: v } } : null);

  const save = async () => {
    if (!modal) return;
    setSaving(true);
    try {
      if (modal.mode === "add") {
        const r = await api<DistanceRule>("POST", "/shipping/distance-rules", modal.data);
        setDistanceRules([...distanceRules, r]);
      } else {
        const r = await api<DistanceRule>("PUT", `/shipping/distance-rules/${modal.data.id}`, modal.data);
        setDistanceRules(distanceRules.map(x => x.id === r.id ? r : x));
      }
      setModal(null); showToast("Regra de distância salva!");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
    finally { setSaving(false); }
  };

  const remove = async (id: string) => {
    if (!confirm("Remover regra de distância?")) return;
    try {
      await api("DELETE", `/shipping/distance-rules/${id}`);
      setDistanceRules(distanceRules.filter(r => r.id !== id)); showToast("Removida.");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const toggle = async (r: DistanceRule) => {
    try {
      const u = await api<DistanceRule>("PUT", `/shipping/distance-rules/${r.id}`, { active: !r.active });
      setDistanceRules(distanceRules.map(x => x.id === r.id ? u : x));
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  return (
    <div className="space-y-4">
      <div className="bg-gold/10 border border-gold/30 rounded-xl px-4 py-3 flex gap-2">
        <AlertCircle size={16} className="text-gold flex-shrink-0 mt-0.5" />
        <p className="text-parchment text-xs">Configure as coordenadas da loja na aba Configurações para habilitar o cálculo automático por distância.</p>
      </div>
      <div className="flex justify-end">
        <button onClick={() => setModal({ mode: "add", data: { ...empty } })}
          className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 text-cream font-bold rounded-lg text-sm">
          <Plus size={16} /> Nova Regra
        </button>
      </div>
      <div className="space-y-2">
        {distanceRules.length === 0 && <p className="text-stone text-sm text-center py-8">Nenhuma regra de distância cadastrada.</p>}
        {distanceRules.map(r => (
          <div key={r.id} className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 flex items-center gap-3">
            <Toggle value={r.active} onChange={() => toggle(r)} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-cream font-medium text-sm">{r.name || `${r.km_min}–${r.km_max} km`}</p>
                <Badge active={r.active} />
              </div>
              <div className="flex gap-3 mt-0.5 flex-wrap">
                <span className="text-stone text-xs">{r.km_min}–{r.km_max} km</span>
                <span className="text-stone text-xs">Base: R$ {r.base_fee.toFixed(2)}</span>
                <span className="text-stone text-xs">+R$ {r.fee_per_km.toFixed(2)}/km</span>
                <span className="text-stone text-xs">Mín/Máx: R$ {r.min_fee}–{r.max_fee}</span>
                <span className="text-stone text-xs">⏱ {r.estimated_time_min} min</span>
              </div>
            </div>
            <button onClick={() => setModal({ mode: "edit", data: { ...r } })} className="text-stone hover:text-gold p-1"><Pencil size={16} /></button>
            <button onClick={() => remove(r.id)} className="text-stone hover:text-red-400 p-1"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      {modal && (
        <Modal title={modal.mode === "add" ? "Nova Regra de Distância" : "Editar Regra"} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Input label="Nome (opcional)" value={modal.data.name ?? ""} onChange={v => set("name", v)} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Km mínimo" type="number" step="0.1" value={modal.data.km_min ?? 0} onChange={v => set("km_min", parseFloat(v) || 0)} />
              <Input label="Km máximo" type="number" step="0.1" value={modal.data.km_max ?? 5} onChange={v => set("km_max", parseFloat(v) || 5)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Taxa base (R$)" type="number" step="0.01" value={modal.data.base_fee ?? 0} onChange={v => set("base_fee", parseFloat(v) || 0)} />
              <Input label="Valor por km (R$)" type="number" step="0.01" value={modal.data.fee_per_km ?? 0} onChange={v => set("fee_per_km", parseFloat(v) || 0)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Frete mínimo (R$)" type="number" step="0.01" value={modal.data.min_fee ?? 0} onChange={v => set("min_fee", parseFloat(v) || 0)} />
              <Input label="Frete máximo (R$)" type="number" step="0.01" value={modal.data.max_fee ?? 999} onChange={v => set("max_fee", parseFloat(v) || 999)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Tempo estimado (min)" type="number" value={modal.data.estimated_time_min ?? 45} onChange={v => set("estimated_time_min", parseInt(v) || 45)} />
              <Input label="Prioridade" type="number" value={modal.data.priority ?? 0} onChange={v => set("priority", parseInt(v) || 0)} />
            </div>
            <div className="flex items-center gap-3"><Toggle value={modal.data.active ?? true} onChange={v => set("active", v)} /><span className="text-parchment text-sm">Ativo</span></div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-surface-03 text-stone rounded-lg text-sm">Cancelar</button>
              <SaveBtn onClick={save} saving={saving} />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── Tab: Order Value Tiers ───────────────────────────────────────────────────

function TabOrderValueTiers({ tiers, setTiers, showToast }: {
  tiers: OrderValueTier[]; setTiers: (t: OrderValueTier[]) => void; showToast: (m: string) => void;
}) {
  const empty: Omit<OrderValueTier, "id"> = {
    name: "", order_value_min: 0, order_value_max: null,
    shipping_value: 0, is_free: false, active: true, priority: 0,
  };
  const [modal, setModal] = useState<{ mode: "add" | "edit"; data: Partial<OrderValueTier> } | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: string, v: unknown) => setModal(m => m ? { ...m, data: { ...m.data, [k]: v } } : null);

  const save = async () => {
    if (!modal) return;
    setSaving(true);
    try {
      if (modal.mode === "add") {
        const t = await api<OrderValueTier>("POST", "/shipping/order-value-tiers", modal.data);
        setTiers([...tiers, t]);
      } else {
        const t = await api<OrderValueTier>("PUT", `/shipping/order-value-tiers/${modal.data.id}`, modal.data);
        setTiers(tiers.map(x => x.id === t.id ? t : x));
      }
      setModal(null); showToast("Faixa salva!");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
    finally { setSaving(false); }
  };

  const remove = async (id: string) => {
    if (!confirm("Remover faixa?")) return;
    try {
      await api("DELETE", `/shipping/order-value-tiers/${id}`);
      setTiers(tiers.filter(t => t.id !== id)); showToast("Removida.");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const toggle = async (t: OrderValueTier) => {
    try {
      const u = await api<OrderValueTier>("PUT", `/shipping/order-value-tiers/${t.id}`, { active: !t.active });
      setTiers(tiers.map(x => x.id === t.id ? u : x));
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setModal({ mode: "add", data: { ...empty } })}
          className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 text-cream font-bold rounded-lg text-sm">
          <Plus size={16} /> Nova Faixa de Valor
        </button>
      </div>
      <div className="space-y-2">
        {tiers.length === 0 && <p className="text-stone text-sm text-center py-8">Nenhuma faixa cadastrada.</p>}
        {tiers.map(t => (
          <div key={t.id} className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 flex items-center gap-3">
            <Toggle value={t.active} onChange={() => toggle(t)} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-cream font-medium text-sm">{t.name || `R$ ${t.order_value_min.toFixed(2)} – ${t.order_value_max != null ? `R$ ${t.order_value_max.toFixed(2)}` : "∞"}`}</p>
                <Badge active={t.active} />
              </div>
              <div className="flex gap-3 mt-0.5">
                <span className="text-stone text-xs">Pedido: R$ {t.order_value_min.toFixed(2)} – {t.order_value_max != null ? `R$ ${t.order_value_max.toFixed(2)}` : "sem limite"}</span>
                <span className={`text-xs ${t.is_free ? "text-green-400" : "text-stone"}`}>{t.is_free ? "Frete Grátis" : `Frete: R$ ${t.shipping_value.toFixed(2)}`}</span>
              </div>
            </div>
            <button onClick={() => setModal({ mode: "edit", data: { ...t } })} className="text-stone hover:text-gold p-1"><Pencil size={16} /></button>
            <button onClick={() => remove(t.id)} className="text-stone hover:text-red-400 p-1"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      {modal && (
        <Modal title={modal.mode === "add" ? "Nova Faixa por Valor" : "Editar Faixa"} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Input label="Nome (opcional)" value={modal.data.name ?? ""} onChange={v => set("name", v)} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Valor mínimo do pedido (R$)" type="number" step="0.01" value={modal.data.order_value_min ?? 0} onChange={v => set("order_value_min", parseFloat(v) || 0)} />
              <Input label="Valor máximo (R$, vazio = sem limite)" type="number" step="0.01"
                value={modal.data.order_value_max ?? ""} onChange={v => set("order_value_max", v ? parseFloat(v) : null)} />
            </div>
            <div className="flex items-center gap-3 py-1">
              <Toggle value={modal.data.is_free ?? false} onChange={v => set("is_free", v)} />
              <span className="text-parchment text-sm">Frete grátis nesta faixa</span>
            </div>
            {!modal.data.is_free && (
              <Input label="Valor do frete (R$)" type="number" step="0.01" value={modal.data.shipping_value ?? 0} onChange={v => set("shipping_value", parseFloat(v) || 0)} />
            )}
            <Input label="Prioridade" type="number" value={modal.data.priority ?? 0} onChange={v => set("priority", parseInt(v) || 0)} />
            <div className="flex items-center gap-3"><Toggle value={modal.data.active ?? true} onChange={v => set("active", v)} /><span className="text-parchment text-sm">Ativo</span></div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-surface-03 text-stone rounded-lg text-sm">Cancelar</button>
              <SaveBtn onClick={save} saving={saving} />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── Tab: Promotions ──────────────────────────────────────────────────────────

function TabPromotions({ promotions, setPromotions, showToast }: {
  promotions: ShippingPromotion[]; setPromotions: (p: ShippingPromotion[]) => void; showToast: (m: string) => void;
}) {
  const empty: Omit<ShippingPromotion, "id"> = {
    name: "", promo_type: "free_above_value", min_order_value: 0,
    shipping_value: 0, neighborhood_ids: "[]", valid_from: null, valid_until: null,
    active: true, priority: 100,
  };
  const [modal, setModal] = useState<{ mode: "add" | "edit"; data: Partial<ShippingPromotion> } | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: string, v: unknown) => setModal(m => m ? { ...m, data: { ...m.data, [k]: v } } : null);

  const promoLabel = (type: string) => PROMO_TYPE_OPTIONS.find(o => o.value === type)?.label ?? type;

  const save = async () => {
    if (!modal) return;
    setSaving(true);
    try {
      if (modal.mode === "add") {
        const p = await api<ShippingPromotion>("POST", "/shipping/promotions", modal.data);
        setPromotions([...promotions, p]);
      } else {
        const p = await api<ShippingPromotion>("PUT", `/shipping/promotions/${modal.data.id}`, modal.data);
        setPromotions(promotions.map(x => x.id === p.id ? p : x));
      }
      setModal(null); showToast("Promoção salva!");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
    finally { setSaving(false); }
  };

  const remove = async (id: string) => {
    if (!confirm("Remover promoção?")) return;
    try {
      await api("DELETE", `/shipping/promotions/${id}`);
      setPromotions(promotions.filter(p => p.id !== id)); showToast("Removida.");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const toggle = async (p: ShippingPromotion) => {
    try {
      const u = await api<ShippingPromotion>("PUT", `/shipping/promotions/${p.id}`, { active: !p.active });
      setPromotions(promotions.map(x => x.id === p.id ? u : x));
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const fmtDate = (d: string | null) => d ? new Date(d).toLocaleDateString("pt-BR") : null;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setModal({ mode: "add", data: { ...empty } })}
          className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 text-cream font-bold rounded-lg text-sm">
          <Plus size={16} /> Nova Promoção
        </button>
      </div>
      <div className="space-y-2">
        {promotions.length === 0 && <p className="text-stone text-sm text-center py-8">Nenhuma promoção cadastrada.</p>}
        {promotions.map(p => (
          <div key={p.id} className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 flex items-center gap-3">
            <Toggle value={p.active} onChange={() => toggle(p)} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-cream font-medium text-sm">{p.name}</p>
                <Badge active={p.active} />
              </div>
              <div className="flex gap-3 mt-0.5 flex-wrap">
                <span className="text-stone text-xs">{promoLabel(p.promo_type)}</span>
                {p.min_order_value > 0 && <span className="text-stone text-xs">Mín: R$ {p.min_order_value.toFixed(2)}</span>}
                <span className={`text-xs ${p.shipping_value === 0 ? "text-green-400" : "text-stone"}`}>{p.shipping_value === 0 ? "Frete Grátis" : `R$ ${p.shipping_value.toFixed(2)}`}</span>
                {p.valid_from && <span className="text-stone text-xs">{fmtDate(p.valid_from)} – {fmtDate(p.valid_until)}</span>}
              </div>
            </div>
            <button onClick={() => setModal({ mode: "edit", data: { ...p } })} className="text-stone hover:text-gold p-1"><Pencil size={16} /></button>
            <button onClick={() => remove(p.id)} className="text-stone hover:text-red-400 p-1"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      {modal && (
        <Modal title={modal.mode === "add" ? "Nova Promoção de Frete" : "Editar Promoção"} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Input label="Nome *" value={modal.data.name ?? ""} onChange={v => set("name", v)} />
            <Select label="Tipo de promoção *" value={modal.data.promo_type ?? "free_above_value"}
              onChange={v => set("promo_type", v)} options={PROMO_TYPE_OPTIONS} />
            {(modal.data.promo_type === "free_above_value" || modal.data.promo_type === "promotional_period") && (
              <Input label="Pedido mínimo (R$)" type="number" step="0.01"
                value={modal.data.min_order_value ?? 0} onChange={v => set("min_order_value", parseFloat(v) || 0)} />
            )}
            {modal.data.promo_type !== "free_above_value" && modal.data.promo_type !== "free_by_neighborhood" && modal.data.promo_type !== "free_campaign" && (
              <Input label="Valor do frete (R$) — 0 = grátis" type="number" step="0.01"
                value={modal.data.shipping_value ?? 0} onChange={v => set("shipping_value", parseFloat(v) || 0)} />
            )}
            {(modal.data.promo_type === "promotional_period" || modal.data.promo_type === "free_campaign") && (
              <div className="grid grid-cols-2 gap-3">
                <Input label="Início (opcional)" type="datetime-local"
                  value={modal.data.valid_from ? modal.data.valid_from.slice(0, 16) : ""}
                  onChange={v => set("valid_from", v ? new Date(v).toISOString() : null)} />
                <Input label="Fim (opcional)" type="datetime-local"
                  value={modal.data.valid_until ? modal.data.valid_until.slice(0, 16) : ""}
                  onChange={v => set("valid_until", v ? new Date(v).toISOString() : null)} />
              </div>
            )}
            <Input label="Prioridade (maior = avaliada primeiro)" type="number"
              value={modal.data.priority ?? 100} onChange={v => set("priority", parseInt(v) || 100)} />
            <div className="flex items-center gap-3"><Toggle value={modal.data.active ?? true} onChange={v => set("active", v)} /><span className="text-parchment text-sm">Ativo</span></div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-surface-03 text-stone rounded-lg text-sm">Cancelar</button>
              <SaveBtn onClick={save} saving={saving} />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── Tab: Extra Rules ─────────────────────────────────────────────────────────

function TabExtras({ extraRules, setExtraRules, showToast }: {
  extraRules: ExtraRule[]; setExtraRules: (r: ExtraRule[]) => void; showToast: (m: string) => void;
}) {
  const empty: Omit<ExtraRule, "id"> = {
    rule_type: "time_surcharge", name: "", value: 0, value_type: "fixed",
    condition: "", message: "", active: true, priority: 0,
    time_start: null, time_end: null,
  };
  const [modal, setModal] = useState<{ mode: "add" | "edit"; data: Partial<ExtraRule> } | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (k: string, v: unknown) => setModal(m => m ? { ...m, data: { ...m.data, [k]: v } } : null);

  const extraLabel = (type: string) => EXTRA_TYPE_OPTIONS.find(o => o.value === type)?.label ?? type;

  const save = async () => {
    if (!modal) return;
    setSaving(true);
    try {
      if (modal.mode === "add") {
        const r = await api<ExtraRule>("POST", "/shipping/extra-rules", modal.data);
        setExtraRules([...extraRules, r]);
      } else {
        const r = await api<ExtraRule>("PUT", `/shipping/extra-rules/${modal.data.id}`, modal.data);
        setExtraRules(extraRules.map(x => x.id === r.id ? r : x));
      }
      setModal(null); showToast("Regra salva!");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
    finally { setSaving(false); }
  };

  const remove = async (id: string) => {
    if (!confirm("Remover regra extra?")) return;
    try {
      await api("DELETE", `/shipping/extra-rules/${id}`);
      setExtraRules(extraRules.filter(r => r.id !== id)); showToast("Removida.");
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const toggle = async (r: ExtraRule) => {
    try {
      const u = await api<ExtraRule>("PUT", `/shipping/extra-rules/${r.id}`, { active: !r.active });
      setExtraRules(extraRules.map(x => x.id === r.id ? u : x));
    } catch (e: unknown) { showToast(`Erro: ${(e as Error).message}`); }
  };

  const typeColor: Record<string, string> = {
    time_surcharge: "text-blue-400", demand_surcharge: "text-orange-400",
    area_surcharge: "text-purple-400", scheduled_surcharge: "text-cyan-400",
    region_block: "text-red-400",
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => setModal({ mode: "add", data: { ...empty } })}
          className="flex items-center gap-2 px-4 py-2 bg-gold hover:bg-gold/90 text-cream font-bold rounded-lg text-sm">
          <Plus size={16} /> Nova Regra Extra
        </button>
      </div>
      <div className="space-y-2">
        {extraRules.length === 0 && <p className="text-stone text-sm text-center py-8">Nenhuma regra extra cadastrada.</p>}
        {extraRules.map(r => (
          <div key={r.id} className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 flex items-center gap-3">
            <Toggle value={r.active} onChange={() => toggle(r)} />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-cream font-medium text-sm">{r.name}</p>
                <span className={`text-xs font-medium ${typeColor[r.rule_type] ?? "text-stone"}`}>{extraLabel(r.rule_type)}</span>
                <Badge active={r.active} />
              </div>
              <div className="flex gap-3 mt-0.5 flex-wrap">
                {r.rule_type !== "region_block" && (
                  <span className="text-stone text-xs">{r.value_type === "percentage" ? `+${r.value}%` : `+R$ ${r.value.toFixed(2)}`}</span>
                )}
                {r.condition && <span className="text-stone text-xs">Área: {r.condition}</span>}
                {r.time_start && <span className="text-stone text-xs">⏰ {r.time_start}–{r.time_end}</span>}
                {r.message && <span className="text-stone text-xs italic">"{r.message}"</span>}
              </div>
            </div>
            <button onClick={() => setModal({ mode: "edit", data: { ...r } })} className="text-stone hover:text-gold p-1"><Pencil size={16} /></button>
            <button onClick={() => remove(r.id)} className="text-stone hover:text-red-400 p-1"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      {modal && (
        <Modal title={modal.mode === "add" ? "Nova Regra Extra" : "Editar Regra Extra"} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Input label="Nome *" value={modal.data.name ?? ""} onChange={v => set("name", v)} />
            <Select label="Tipo de regra *" value={modal.data.rule_type ?? "time_surcharge"}
              onChange={v => set("rule_type", v)} options={EXTRA_TYPE_OPTIONS} />
            {modal.data.rule_type !== "region_block" && (
              <div className="grid grid-cols-2 gap-3">
                <Input label="Valor" type="number" step="0.01" value={modal.data.value ?? 0} onChange={v => set("value", parseFloat(v) || 0)} />
                <Select label="Tipo de valor" value={modal.data.value_type ?? "fixed"}
                  onChange={v => set("value_type", v)}
                  options={[{ value: "fixed", label: "Valor fixo (R$)" }, { value: "percentage", label: "Percentual (%)" }]} />
              </div>
            )}
            {(modal.data.rule_type === "area_surcharge" || modal.data.rule_type === "region_block") && (
              <Input label="Bairro / Cidade (condição)" value={modal.data.condition ?? ""} onChange={v => set("condition", v)}
                placeholder="Ex: Centro, Vila Madalena..." />
            )}
            {modal.data.rule_type === "time_surcharge" && (
              <div className="grid grid-cols-2 gap-3">
                <Input label="Hora início (HH:MM)" value={modal.data.time_start ?? ""} onChange={v => set("time_start", v || null)} placeholder="18:00" />
                <Input label="Hora fim (HH:MM)" value={modal.data.time_end ?? ""} onChange={v => set("time_end", v || null)} placeholder="23:00" />
              </div>
            )}
            <Textarea label="Mensagem (exibida ao cliente)" value={modal.data.message ?? ""} onChange={v => set("message", v)} />
            <Input label="Prioridade" type="number" value={modal.data.priority ?? 0} onChange={v => set("priority", parseInt(v) || 0)} />
            <div className="flex items-center gap-3"><Toggle value={modal.data.active ?? true} onChange={v => set("active", v)} /><span className="text-parchment text-sm">Ativo</span></div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 border border-surface-03 text-stone rounded-lg text-sm">Cancelar</button>
              <SaveBtn onClick={save} saving={saving} />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
