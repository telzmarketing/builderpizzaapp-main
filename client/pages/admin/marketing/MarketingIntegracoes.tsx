import { useEffect, useState } from "react";
import { Loader2, ChevronDown, ChevronUp, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unwrap = (json: any) => json?.data ?? json;

interface Integration {
  id: string;
  name: string;
  type: string;
  connected: boolean;
  config?: Record<string, string>;
}

interface IntegrationDef {
  type: string;
  label: string;
  emoji: string;
  description: string;
  fields: { key: string; label: string; placeholder: string; secret?: boolean }[];
}

const INTEGRATIONS: IntegrationDef[] = [
  {
    type: "meta_ads",
    label: "Meta Ads",
    emoji: "📘",
    description: "Conecte sua conta do Facebook/Instagram Ads para rastrear conversões e otimizar campanhas.",
    fields: [
      { key: "pixel_id", label: "Pixel ID", placeholder: "1234567890" },
      { key: "access_token", label: "Access Token", placeholder: "EAABsb...", secret: true },
    ],
  },
  {
    type: "google_ads",
    label: "Google Ads",
    emoji: "🎯",
    description: "Integre com o Google Ads para acompanhar conversões e sincronizar audiências.",
    fields: [
      { key: "conversion_id", label: "Conversion ID", placeholder: "AW-1234567890" },
      { key: "api_key", label: "API Key", placeholder: "AIza...", secret: true },
    ],
  },
  {
    type: "tiktok_ads",
    label: "TikTok Ads",
    emoji: "🎵",
    description: "Integre com o TikTok Ads Manager para rastrear eventos e conversões.",
    fields: [
      { key: "pixel_id", label: "Pixel ID", placeholder: "CXXXXXXXXXXXXXXXX" },
      { key: "access_token", label: "Access Token", placeholder: "...", secret: true },
    ],
  },
  {
    type: "whatsapp_cloud",
    label: "WhatsApp Cloud API",
    emoji: "💬",
    description: "Envie mensagens automáticas via API oficial do WhatsApp Business Cloud.",
    fields: [
      { key: "phone_number_id", label: "Phone Number ID", placeholder: "1234567890" },
      { key: "access_token", label: "Access Token", placeholder: "EAABsb...", secret: true },
      { key: "waba_id", label: "WABA ID", placeholder: "1234567890" },
    ],
  },
  {
    type: "whatsapp_qr",
    label: "WhatsApp QR Code",
    emoji: "📱",
    description: "Conecte via QR Code para enviar mensagens pelo WhatsApp pessoal ou Business.",
    fields: [
      { key: "session_name", label: "Nome da sessão", placeholder: "moschettieri" },
      { key: "webhook_url", label: "Webhook URL", placeholder: "https://..." },
    ],
  },
  {
    type: "smtp",
    label: "SMTP / E-mail",
    emoji: "📧",
    description: "Configure o servidor SMTP para envio de e-mails transacionais e campanhas.",
    fields: [
      { key: "host", label: "Host SMTP", placeholder: "smtp.gmail.com" },
      { key: "port", label: "Porta", placeholder: "587" },
      { key: "user", label: "Usuário", placeholder: "seu@email.com" },
      { key: "password", label: "Senha / App Password", placeholder: "...", secret: true },
      { key: "from_name", label: "Nome remetente", placeholder: "Moschettieri Pizzaria" },
    ],
  },
];

export default function MarketingIntegracoes() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [configs, setConfigs] = useState<Record<string, Record<string, string>>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { ok: boolean; message: string }>>({});

  const token = localStorage.getItem("admin_token");
  const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const fetchIntegrations = () => {
    setLoading(true);
    setError("");
    fetch(`${BASE}/marketing/integrations`, { headers })
      .then((r) => { if (!r.ok) throw new Error("Falha ao carregar integrações."); return r.json(); })
      .then(unwrap)
      .then((data: Integration[]) => {
        setIntegrations(data);
        const initial: Record<string, Record<string, string>> = {};
        data.forEach((i) => { if (i.config) initial[i.type] = i.config; });
        setConfigs(initial);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchIntegrations(); }, []);

  const getStatus = (type: string) =>
    integrations.find((i) => i.type === type)?.connected ?? false;

  const handleSave = async (type: string) => {
    setSaving(type);
    try {
      await fetch(`${BASE}/marketing/integrations/${type}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ config: configs[type] ?? {} }),
      });
      fetchIntegrations();
    } catch {
      alert("Erro ao salvar integração.");
    } finally {
      setSaving(null);
    }
  };

  const handleTest = async (type: string) => {
    setTesting(type);
    setTestResult((prev) => ({ ...prev, [type]: { ok: false, message: "Testando..." } }));
    try {
      const res = await fetch(`${BASE}/marketing/integrations/${type}/test`, {
        method: "POST",
        headers,
      });
      const data = await res.json();
      setTestResult((prev) => ({
        ...prev,
        [type]: { ok: res.ok, message: data?.message ?? (res.ok ? "Conexão bem-sucedida!" : "Falha na conexão.") },
      }));
    } catch {
      setTestResult((prev) => ({ ...prev, [type]: { ok: false, message: "Erro de rede." } }));
    } finally {
      setTesting(null);
    }
  };

  const updateConfig = (type: string, key: string, value: string) => {
    setConfigs((prev) => ({
      ...prev,
      [type]: { ...(prev[type] ?? {}), [key]: value },
    }));
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-surface-01">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-gold mb-1">Marketing</p>
            <h1 className="text-2xl font-bold text-cream">Integrações</h1>
          </div>
          <button
            onClick={fetchIntegrations}
            className="p-2 rounded-xl bg-surface-02 border border-surface-03 text-stone hover:text-cream transition-colors"
          >
            <RefreshCw size={16} />
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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {INTEGRATIONS.map((def) => {
              const connected = getStatus(def.type);
              const isExpanded = expanded === def.type;
              const test = testResult[def.type];

              return (
                <div
                  key={def.type}
                  className="bg-surface-02 border border-surface-03 rounded-2xl overflow-hidden"
                >
                  <div className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{def.emoji}</span>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-cream font-semibold text-sm">{def.label}</h3>
                            {connected ? (
                              <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 px-2 py-0.5 rounded-full">
                                <CheckCircle2 size={10} /> Conectado
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-xs text-stone bg-surface-03 px-2 py-0.5 rounded-full">
                                <XCircle size={10} /> Desconectado
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-stone mt-1 leading-relaxed">{def.description}</p>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 mt-4">
                      <button
                        onClick={() => setExpanded(isExpanded ? null : def.type)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gold hover:bg-gold/90 text-black text-xs font-semibold transition-colors"
                      >
                        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        {connected ? "Configurar" : "Conectar"}
                      </button>
                      <button
                        onClick={() => handleTest(def.type)}
                        disabled={testing === def.type || !connected}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-surface-03 text-stone hover:text-cream text-xs transition-colors disabled:opacity-40"
                      >
                        {testing === def.type ? <Loader2 size={12} className="animate-spin" /> : null}
                        Testar
                      </button>
                    </div>

                    {test && (
                      <p className={`mt-2 text-xs ${test.ok ? "text-green-400" : "text-red-400"}`}>
                        {test.message}
                      </p>
                    )}
                  </div>

                  {/* Expanded fields */}
                  {isExpanded && (
                    <div className="border-t border-surface-03 p-5 space-y-4 bg-surface-03/20">
                      {def.fields.map((f) => (
                        <div key={f.key} className="space-y-1">
                          <label className="text-xs text-stone">{f.label}</label>
                          <input
                            type={f.secret ? "password" : "text"}
                            value={configs[def.type]?.[f.key] ?? ""}
                            onChange={(e) => updateConfig(def.type, f.key, e.target.value)}
                            placeholder={f.placeholder}
                            autoComplete="off"
                            className="w-full bg-surface-03 border border-surface-03 rounded-xl px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
                          />
                        </div>
                      ))}
                      <div className="flex gap-2 pt-1">
                        <button
                          onClick={() => setExpanded(null)}
                          className="flex-1 py-2 rounded-xl border border-surface-03 text-stone hover:text-cream text-sm transition-colors"
                        >
                          Cancelar
                        </button>
                        <button
                          onClick={() => handleSave(def.type)}
                          disabled={saving === def.type}
                          className="flex-1 py-2 rounded-xl bg-gold hover:bg-gold/90 text-black font-semibold text-sm transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                        >
                          {saving === def.type && <Loader2 size={14} className="animate-spin" />}
                          Salvar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
