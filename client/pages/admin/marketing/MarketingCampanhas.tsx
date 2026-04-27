import { useEffect, useState } from "react";
import {
  Loader2, Plus, Pencil, Trash2, X, Megaphone,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

type CampaignStatus = "draft" | "active" | "paused" | "ended";
type CampaignChannel = "whatsapp" | "email" | "paid_traffic" | "internal";
type CampaignType =
  | "paid_traffic"
  | "whatsapp"
  | "email"
  | "internal"
  | "remarketing"
  | "abandoned_cart"
  | "reactivation"
  | "birthday";

interface Campaign {
  id: string;
  name: string;
  type: CampaignType;
  channel: CampaignChannel;
  status: CampaignStatus;
  budget: number;
  spent: number;
  revenue: number;
  roas: number;
  orders: number;
  start_date: string;
  end_date: string;
  destination_url?: string;
  description?: string;
}

const STATUS_COLORS: Record<CampaignStatus, string> = {
  draft: "bg-surface-03 text-stone",
  active: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  ended: "bg-red-500/20 text-red-400",
};
const STATUS_LABELS: Record<CampaignStatus, string> = {
  draft: "Rascunho",
  active: "Ativo",
  paused: "Pausado",
  ended: "Encerrado",
};
const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  email: "E-mail",
  paid_traffic: "Tráfego Pago",
  internal: "Interno",
};
const TYPE_LABELS: Record<CampaignType, string> = {
  paid_traffic: "Tráfego Pago",
  whatsapp: "WhatsApp",
  email: "E-mail",
  internal: "Interno",
  remarketing: "Remarketing",
  abandoned_cart: "Carrinho Abandonado",
  reactivation: "Reativação",
  birthday: "Aniversário",
};

function fmt(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const emptyForm = (): Partial<Campaign> => ({
  name: "",
  type: "paid_traffic",
  channel: "paid_traffic",
  budget: 0,
  start_date: "",
  end_date: "",
  destination_url: "",
  description: "",
});

export default function MarketingCampanhas() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Partial<Campaign>>(emptyForm());
  const [saving, setSaving] = useState(false);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchCampaigns = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/marketing/campaigns`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar campanhas."); return r.json(); })
      .then(unwrap)
      .then(setCampaigns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchCampaigns(); }, []);

  const filtered = campaigns.filter((c) => {
    if (statusFilter !== "all" && c.status !== statusFilter) return false;
    if (channelFilter !== "all" && c.channel !== channelFilter) return false;
    return true;
  });

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm());
    setShowModal(true);
  };

  const openEdit = (c: Campaign) => {
    setEditingId(c.id);
    setForm({ ...c });
    setShowModal(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name?.trim()) { alert("Nome obrigatório."); return; }
    setSaving(true);
    try {
      if (editingId) {
        await fetch(`${BASE}/marketing/campaigns/${editingId}`, {
          method: "PATCH",
          headers,
          body: JSON.stringify(form),
        });
      } else {
        await fetch(`${BASE}/marketing/campaigns`, {
          method: "POST",
          headers,
          body: JSON.stringify(form),
        });
      }
      setShowModal(false);
      fetchCampaigns();
    } catch {
      alert("Erro ao salvar campanha.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Excluir campanha?")) return;
    await fetch(`${BASE}/marketing/campaigns/${id}`, { method: "DELETE", headers });
    fetchCampaigns();
  };

  const field = (key: keyof Campaign, label: string, type = "text", opts?: { placeholder?: string }) => (
    <div className="space-y-1">
      <label className="text-xs text-stone">{label}</label>
      <input
        type={type}
        value={(form[key] as string | number | undefined) ?? ""}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        placeholder={opts?.placeholder}
        className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
      />
    </div>
  );

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Central de Campanhas</h1>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
          >
            <Plus size={16} /> Nova Campanha
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
            {["all", "active", "paused", "draft", "ended"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-2 text-xs font-medium transition-colors ${statusFilter === s ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
              >
                {s === "all" ? "Todos" : STATUS_LABELS[s as CampaignStatus] ?? s}
              </button>
            ))}
          </div>
          <div className="flex bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
            {["all", "whatsapp", "email", "paid_traffic", "internal"].map((ch) => (
              <button
                key={ch}
                onClick={() => setChannelFilter(ch)}
                className={`px-3 py-2 text-xs font-medium transition-colors ${channelFilter === ch ? "bg-gold text-black" : "text-stone hover:text-cream"}`}
              >
                {ch === "all" ? "Todos" : CHANNEL_LABELS[ch] ?? ch}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 className="animate-spin text-gold" size={28} />
          </div>
        )}
        {error && !loading && (
          <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">{error}</div>
        )}

        {!loading && !error && (
          <div className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden">
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Megaphone size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhuma campanha encontrada.</p>
                <button onClick={openCreate} className="mt-4 text-gold text-sm hover:underline">
                  Criar primeira campanha
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                      <th className="text-left p-3">Nome</th>
                      <th className="text-left p-3">Tipo</th>
                      <th className="text-left p-3">Canal</th>
                      <th className="text-left p-3">Status</th>
                      <th className="text-right p-3">Orçamento</th>
                      <th className="text-right p-3">Gasto</th>
                      <th className="text-right p-3">Receita</th>
                      <th className="text-right p-3">ROAS</th>
                      <th className="text-right p-3">Pedidos</th>
                      <th className="text-left p-3">Datas</th>
                      <th className="p-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-03">
                    {filtered.map((c) => (
                      <tr key={c.id} className="hover:bg-surface-03/30 transition-colors">
                        <td className="p-3 font-medium text-cream">{c.name}</td>
                        <td className="p-3 text-stone">{TYPE_LABELS[c.type] ?? c.type}</td>
                        <td className="p-3 text-stone">{CHANNEL_LABELS[c.channel] ?? c.channel}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[c.status]}`}>
                            {STATUS_LABELS[c.status]}
                          </span>
                        </td>
                        <td className="p-3 text-right text-stone">{fmt(c.budget)}</td>
                        <td className="p-3 text-right text-red-400">{fmt(c.spent)}</td>
                        <td className="p-3 text-right text-green-400">{fmt(c.revenue)}</td>
                        <td className="p-3 text-right text-gold font-semibold">{c.roas.toFixed(2)}x</td>
                        <td className="p-3 text-right text-cream">{c.orders}</td>
                        <td className="p-3 text-stone text-xs whitespace-nowrap">
                          {c.start_date?.slice(0, 10)} → {c.end_date?.slice(0, 10)}
                        </td>
                        <td className="p-3">
                          <div className="flex gap-1 justify-end">
                            <button
                              onClick={() => openEdit(c)}
                              className="p-1.5 rounded-lg hover:bg-surface-03 text-stone hover:text-cream transition-colors"
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => handleDelete(c.id)}
                              className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Modal */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">
                  {editingId ? "Editar Campanha" : "Nova Campanha"}
                </h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSave} className="p-5 space-y-4">
                {field("name", "Nome da campanha *", "text", { placeholder: "Ex: Campanha Black Friday" })}

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Tipo</label>
                    <select
                      value={form.type ?? "paid_traffic"}
                      onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as CampaignType }))}
                      className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
                    >
                      {Object.entries(TYPE_LABELS).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">Canal</label>
                    <select
                      value={form.channel ?? "paid_traffic"}
                      onChange={(e) => setForm((f) => ({ ...f, channel: e.target.value as CampaignChannel }))}
                      className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
                    >
                      {Object.entries(CHANNEL_LABELS).map(([v, l]) => (
                        <option key={v} value={v}>{l}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">Orçamento (R$)</label>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={form.budget ?? 0}
                    onChange={(e) => setForm((f) => ({ ...f, budget: parseFloat(e.target.value) || 0 }))}
                    className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {field("start_date", "Data início", "date")}
                  {field("end_date", "Data fim", "date")}
                </div>

                {field("destination_url", "URL destino", "url", { placeholder: "https://..." })}

                <div className="space-y-1">
                  <label className="text-xs text-stone">Descrição</label>
                  <textarea
                    value={form.description ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    rows={3}
                    className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold resize-none"
                  />
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                  >
                    {saving && <Loader2 size={14} className="animate-spin" />}
                    {editingId ? "Salvar" : "Criar"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
