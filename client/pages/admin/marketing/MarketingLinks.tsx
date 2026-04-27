import { useEffect, useState } from "react";
import {
  Loader2, Plus, Copy, Check, Trash2, X, Link2, ExternalLink,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;
const STORE_DOMAIN = (import.meta.env.VITE_STORE_DOMAIN ?? "delivery.moschettieri.com.br");

interface TrackingLink {
  id: string;
  slug: string;
  destination_url: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  clicks: number;
  unique_clicks: number;
  orders: number;
  revenue: number;
  created_at: string;
}

const emptyForm = (): Partial<TrackingLink> => ({
  slug: "",
  destination_url: "",
  utm_source: "",
  utm_medium: "",
  utm_campaign: "",
});

function fmt(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function MarketingLinks() {
  const [links, setLinks] = useState<TrackingLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<Partial<TrackingLink>>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchLinks = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/marketing/tracking-links`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar links."); return r.json(); })
      .then(unwrap)
      .then(setLinks)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchLinks(); }, []);

  const fullUrl = (slug: string) => `https://${STORE_DOMAIN}/r/${slug}`;

  const handleCopy = (slug: string) => {
    navigator.clipboard.writeText(fullUrl(slug));
    setCopied(slug);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.slug?.trim()) { alert("Slug obrigatório."); return; }
    if (!form.destination_url?.trim()) { alert("URL destino obrigatória."); return; }
    const kebab = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
    if (!kebab.test(form.slug)) { alert("Slug deve estar em kebab-case (letras minúsculas e hífens)."); return; }
    setSaving(true);
    try {
      const res = await fetch(`${BASE}/marketing/tracking-links`, {
        method: "POST",
        headers,
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail ?? "Erro ao criar link.");
      }
      setShowModal(false);
      setForm(emptyForm());
      fetchLinks();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Excluir link rastreável?")) return;
    await fetch(`${BASE}/marketing/tracking-links/${id}`, { method: "DELETE", headers });
    fetchLinks();
  };

  const inputCls = "w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold";

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Links Rastreáveis</h1>
          </div>
          <button
            onClick={() => { setForm(emptyForm()); setShowModal(true); }}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-black font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
          >
            <Plus size={16} /> Novo Link
          </button>
        </div>

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
            {links.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Link2 size={40} className="text-surface-03 mb-3" />
                <p className="text-stone text-sm">Nenhum link criado ainda.</p>
                <button
                  onClick={() => { setForm(emptyForm()); setShowModal(true); }}
                  className="mt-4 text-gold text-sm hover:underline"
                >
                  Criar primeiro link
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-stone text-xs border-b border-surface-03 bg-surface-03/30">
                      <th className="text-left p-3">Slug / URL</th>
                      <th className="text-right p-3">Cliques</th>
                      <th className="text-right p-3">Únicos</th>
                      <th className="text-right p-3">Pedidos</th>
                      <th className="text-right p-3">Receita</th>
                      <th className="text-left p-3">Criado em</th>
                      <th className="p-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-03">
                    {links.map((l) => (
                      <tr key={l.id} className="hover:bg-surface-03/30 transition-colors">
                        <td className="p-3">
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <code className="text-gold font-mono text-xs bg-gold/10 px-2 py-0.5 rounded">
                                /r/{l.slug}
                              </code>
                              <button
                                onClick={() => handleCopy(l.slug)}
                                className="text-stone hover:text-cream transition-colors"
                                title="Copiar URL"
                              >
                                {copied === l.slug ? (
                                  <Check size={14} className="text-green-400" />
                                ) : (
                                  <Copy size={14} />
                                )}
                              </button>
                              <a
                                href={fullUrl(l.slug)}
                                target="_blank"
                                rel="noreferrer"
                                className="text-stone hover:text-cream transition-colors"
                              >
                                <ExternalLink size={14} />
                              </a>
                            </div>
                            <p className="text-stone text-xs truncate max-w-xs">{l.destination_url}</p>
                          </div>
                        </td>
                        <td className="p-3 text-right text-cream">{l.clicks.toLocaleString("pt-BR")}</td>
                        <td className="p-3 text-right text-cream">{l.unique_clicks.toLocaleString("pt-BR")}</td>
                        <td className="p-3 text-right text-cream">{l.orders}</td>
                        <td className="p-3 text-right text-green-400">{fmt(l.revenue)}</td>
                        <td className="p-3 text-stone text-xs">
                          {l.created_at ? new Date(l.created_at).toLocaleDateString("pt-BR") : "—"}
                        </td>
                        <td className="p-3">
                          <button
                            onClick={() => handleDelete(l.id)}
                            className="p-1.5 rounded-lg hover:bg-red-500/10 text-stone hover:text-red-400 transition-colors"
                          >
                            <Trash2 size={14} />
                          </button>
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
            <div className="bg-surface-02 border border-surface-03 rounded-2xl w-full max-w-md">
              <div className="flex items-center justify-between p-5 border-b border-surface-03">
                <h2 className="text-cream font-semibold">Novo Link Rastreável</h2>
                <button onClick={() => setShowModal(false)} className="text-stone hover:text-cream">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSave} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-stone">Slug (kebab-case) *</label>
                  <div className="flex items-center bg-surface-03 border border-surface-03 rounded-xl overflow-hidden focus-within:border-gold">
                    <span className="px-3 text-stone text-sm">/r/</span>
                    <input
                      type="text"
                      value={form.slug ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") }))}
                      placeholder="meu-link"
                      className="flex-1 bg-transparent py-2 pr-3 text-cream text-sm focus:outline-none"
                    />
                  </div>
                  <p className="text-xs text-stone/60">Somente letras minúsculas e hífens.</p>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">URL Destino *</label>
                  <input
                    type="url"
                    value={form.destination_url ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, destination_url: e.target.value }))}
                    placeholder="https://delivery.moschettieri.com.br/..."
                    className={inputCls}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-stone">UTM Source</label>
                  <input
                    type="text"
                    value={form.utm_source ?? ""}
                    onChange={(e) => setForm((f) => ({ ...f, utm_source: e.target.value }))}
                    placeholder="facebook"
                    className={inputCls}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-stone">UTM Medium</label>
                    <input
                      type="text"
                      value={form.utm_medium ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, utm_medium: e.target.value }))}
                      placeholder="cpc"
                      className={inputCls}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-stone">UTM Campaign</label>
                    <input
                      type="text"
                      value={form.utm_campaign ?? ""}
                      onChange={(e) => setForm((f) => ({ ...f, utm_campaign: e.target.value }))}
                      placeholder="black-friday"
                      className={inputCls}
                    />
                  </div>
                </div>

                {form.slug && (
                  <div className="rounded-xl bg-surface-03 p-3 space-y-1">
                    <p className="text-xs text-stone">URL gerada:</p>
                    <p className="text-xs text-gold font-mono break-all">{fullUrl(form.slug)}</p>
                  </div>
                )}

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
                    Criar Link
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
