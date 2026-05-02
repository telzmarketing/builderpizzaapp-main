import { useState, useEffect } from "react";
import { Save, Eye, EyeOff, CheckCircle, AlertCircle, Loader2, CreditCard, QrCode, Wallet, Banknote } from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  adminApi,
  type ApiPaymentGatewayConfig,
  type ApiPaymentGatewayConfigUpdate,
} from "@/lib/api";

type Gateway = "mock" | "mercadopago" | "stripe" | "pagseguro";

type GatewayConfig = ApiPaymentGatewayConfig & { gateway: Gateway };

const GATEWAYS: { id: Gateway; label: string; icon: string; description: string; color: string }[] = [
  {
    id: "mock",
    label: "Modo Teste (Mock)",
    icon: "🧪",
    description: "Simula pagamentos localmente. Nenhum dado real é processado.",
    color: "border-slate-500 bg-slate-500/10",
  },
  {
    id: "mercadopago",
    label: "Mercado Pago",
    icon: "💙",
    description: "PIX, cartão de crédito/débito. Gateway mais usado no Brasil.",
    color: "border-blue-500 bg-blue-500/10",
  },
  {
    id: "stripe",
    label: "Stripe",
    icon: "⚡",
    description: "Cartão de crédito internacional. Ideal para escalar globalmente.",
    color: "border-purple-500 bg-purple-500/10",
  },
  {
    id: "pagseguro",
    label: "PagSeguro",
    icon: "🟡",
    description: "PIX e cartão. Solução completa da UOL para o mercado brasileiro.",
    color: "border-yellow-500 bg-yellow-500/10",
  },
];

export default function AdminPagamentos() {
  const [config, setConfig] = useState<GatewayConfig | null>(null);
  const [form, setForm] = useState<Record<string, string | boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  useEffect(() => {
    adminApi.getPaymentGateway()
      .then((data) => {
        const gatewayData = data as GatewayConfig;
        setConfig(gatewayData);
        setForm({
          gateway: gatewayData.gateway,
          sandbox: gatewayData.sandbox,
          accept_pix: gatewayData.accept_pix,
          accept_credit_card: gatewayData.accept_credit_card,
          accept_debit_card: gatewayData.accept_debit_card,
          accept_cash: gatewayData.accept_cash,
          mp_public_key: gatewayData.mp_public_key || "",
          mp_access_token: "",
          mp_webhook_secret: "",
          stripe_publishable_key: gatewayData.stripe_publishable_key || "",
          stripe_secret_key: "",
          stripe_webhook_secret: "",
          pagseguro_email: gatewayData.pagseguro_email || "",
          pagseguro_token: "",
        });
      })
      .catch(() => setError("Não foi possível carregar a configuração. O backend está rodando?"))
      .finally(() => setLoading(false));
  }, []);

  const set = (key: string, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const toggleSecret = (key: string) =>
    setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      // Send only non-empty strings for secrets (empty = don't update)
      const payload: Record<string, string | boolean | null> = {};
      for (const [key, value] of Object.entries(form)) {
        if (value === "" && ["mp_access_token", "mp_webhook_secret", "stripe_secret_key",
          "stripe_webhook_secret", "pagseguro_token"].includes(key)) {
          continue; // skip blank secret fields
        }
        payload[key] = value;
      }

      const updated = await adminApi.updatePaymentGateway(payload as ApiPaymentGatewayConfigUpdate) as GatewayConfig;
      setConfig(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  };

  const selectedGateway = (form.gateway as Gateway) || "mock";
  const webhookUrl = selectedGateway === "mercadopago"
    ? `${window.location.origin}/api/webhooks/mercadopago`
    : `${window.location.origin}/api/payments/webhook`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          {/* Header */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex justify-between items-center sticky top-0 z-20">
            <div>
              <h2 className="text-2xl font-bold text-cream">Gateway de Pagamento</h2>
              <p className="text-stone text-sm mt-0.5">
                Configure o processador de pagamentos da loja
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSave}
                disabled={saving || loading}
                className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 px-5 rounded-lg transition-colors"
              >
                {saving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                {saving ? "Salvando..." : "Salvar"}
              </button>
              <AdminTopActions />
            </div>
          </div>

          <div className="p-8 space-y-8">
            {/* Feedback */}
            {error && (
              <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/40 rounded-xl px-4 py-3 text-red-400">
                <AlertCircle size={20} />
                <span className="text-sm">{error}</span>
              </div>
            )}
            {saved && (
              <div className="flex items-center gap-3 bg-green-500/10 border border-green-500/40 rounded-xl px-4 py-3 text-green-400">
                <CheckCircle size={20} />
                <span className="text-sm">Configuração salva com sucesso!</span>
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 size={40} className="animate-spin text-orange-500" />
              </div>
            ) : (
              <>
                {/* ── Gateway selector ───────────────────────────────────── */}
                <section className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                  <div className="px-6 py-4 border-b border-surface-03">
                    <h3 className="text-lg font-bold text-cream">Processador de Pagamento</h3>
                    <p className="text-stone text-sm">Selecione o gateway ativo para a loja</p>
                  </div>
                  <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {GATEWAYS.map((gw) => (
                      <button
                        key={gw.id}
                        onClick={() => set("gateway", gw.id)}
                        className={`flex items-start gap-4 p-4 rounded-xl border-2 text-left transition-all ${
                          selectedGateway === gw.id
                            ? gw.color + " border-opacity-100"
                            : "border-surface-03 hover:border-slate-500"
                        }`}
                      >
                        <span className="text-3xl mt-0.5">{gw.icon}</span>
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <p className="text-cream font-bold text-sm">{gw.label}</p>
                            {selectedGateway === gw.id && (
                              <span className="text-xs bg-gold text-cream px-2 py-0.5 rounded-full">Ativo</span>
                            )}
                          </div>
                          <p className="text-stone text-xs mt-1 leading-relaxed">{gw.description}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </section>

                {/* ── Ambiente ──────────────────────────────────────────── */}
                <section className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                  <div className="px-6 py-4 border-b border-surface-03">
                    <h3 className="text-lg font-bold text-cream">Ambiente</h3>
                  </div>
                  <div className="p-6 flex gap-4">
                    {[
                      { value: true, label: "🧪 Sandbox (Testes)", desc: "Nenhum valor real é cobrado" },
                      { value: false, label: "🚀 Produção", desc: "Pagamentos reais — ative com cuidado" },
                    ].map((opt) => (
                      <button
                        key={String(opt.value)}
                        onClick={() => set("sandbox", opt.value)}
                        className={`flex-1 p-4 rounded-xl border-2 text-left transition-all ${
                          form.sandbox === opt.value
                            ? "border-gold bg-gold/10"
                            : "border-surface-03 hover:border-slate-500"
                        }`}
                      >
                        <p className="text-cream font-bold text-sm">{opt.label}</p>
                        <p className="text-stone text-xs mt-1">{opt.desc}</p>
                      </button>
                    ))}
                  </div>
                </section>

                {/* ── Métodos aceitos ───────────────────────────────────── */}
                <section className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                  <div className="px-6 py-4 border-b border-surface-03">
                    <h3 className="text-lg font-bold text-cream">Métodos de Pagamento Aceitos</h3>
                  </div>
                  <div className="p-6 grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { key: "accept_pix", icon: QrCode, label: "PIX" },
                      { key: "accept_credit_card", icon: CreditCard, label: "Cartão de Crédito" },
                      { key: "accept_debit_card", icon: Wallet, label: "Cartão de Débito" },
                      { key: "accept_cash", icon: Banknote, label: "Dinheiro" },
                    ].map(({ key, icon: Icon, label }) => (
                      <button
                        key={key}
                        onClick={() => set(key, !form[key])}
                        className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                          form[key]
                            ? "border-gold bg-gold/10 text-orange-400"
                            : "border-surface-03 text-stone/70 hover:border-slate-500"
                        }`}
                      >
                        <Icon size={24} />
                        <span className="text-sm font-medium text-center">{label}</span>
                      </button>
                    ))}
                  </div>
                </section>

                {/* ── Mercado Pago credentials ──────────────────────────── */}
                {selectedGateway === "mercadopago" && (
                  <CredentialSection
                    title="Credenciais — Mercado Pago"
                    badge="mp"
                    docUrl="https://www.mercadopago.com.br/developers/pt/docs/getting-started"
                    fields={[
                      { key: "mp_public_key", label: "Public Key", placeholder: "APP_USR-...", secret: false },
                      { key: "mp_access_token", label: "Access Token", placeholder: config?.mp_access_token_masked || "Não configurado — cole o novo valor", secret: true },
                      { key: "mp_webhook_secret", label: "Webhook Secret", placeholder: "Cole o segredo do webhook", secret: true },
                    ]}
                    form={form}
                    showSecrets={showSecrets}
                    set={set}
                    toggleSecret={toggleSecret}
                  />
                )}

                {/* ── Stripe credentials ─────────────────────────────────── */}
                {selectedGateway === "stripe" && (
                  <CredentialSection
                    title="Credenciais — Stripe"
                    badge="stripe"
                    docUrl="https://stripe.com/docs/keys"
                    fields={[
                      { key: "stripe_publishable_key", label: "Publishable Key", placeholder: "pk_test_...", secret: false },
                      { key: "stripe_secret_key", label: "Secret Key", placeholder: config?.stripe_secret_key_masked || "Não configurado — cole o novo valor", secret: true },
                      { key: "stripe_webhook_secret", label: "Webhook Secret", placeholder: "whsec_...", secret: true },
                    ]}
                    form={form}
                    showSecrets={showSecrets}
                    set={set}
                    toggleSecret={toggleSecret}
                  />
                )}

                {/* ── PagSeguro credentials ──────────────────────────────── */}
                {selectedGateway === "pagseguro" && (
                  <CredentialSection
                    title="Credenciais — PagSeguro"
                    badge="pagseguro"
                    docUrl="https://dev.pagseguro.uol.com.br/"
                    fields={[
                      { key: "pagseguro_email", label: "E-mail da conta PagSeguro", placeholder: "seu@email.com", secret: false },
                      { key: "pagseguro_token", label: "Token de Integração", placeholder: config?.pagseguro_token_masked || "Não configurado — cole o novo valor", secret: true },
                    ]}
                    form={form}
                    showSecrets={showSecrets}
                    set={set}
                    toggleSecret={toggleSecret}
                  />
                )}

                {/* ── Status e webhook URL ──────────────────────────────── */}
                <section className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
                  <div className="px-6 py-4 border-b border-surface-03">
                    <h3 className="text-lg font-bold text-cream">URL do Webhook</h3>
                    <p className="text-stone text-sm mt-1">
                      Cadastre esta URL no painel do gateway para receber confirmações automáticas
                    </p>
                  </div>
                  <div className="p-6">
                    <div className="flex items-center gap-3 bg-surface-00 rounded-xl px-4 py-3 border border-surface-03">
                      <code className="text-orange-400 text-sm flex-1 break-all">
                        {webhookUrl}
                      </code>
                      <button
                        onClick={() => navigator.clipboard.writeText(webhookUrl)}
                        className="text-stone hover:text-cream text-xs border border-surface-03 rounded px-2 py-1 transition-colors flex-shrink-0"
                      >
                        Copiar
                      </button>
                    </div>
                    <p className="text-stone/70 text-xs mt-2">
                      Em produção, cadastre esta URL no painel do gateway usando o domínio público da loja.
                    </p>

                    {/* Last updated */}
                    {config?.updated_at && (
                      <p className="text-slate-600 text-xs mt-4">
                        Última atualização:{" "}
                        {new Date(config.updated_at).toLocaleString("pt-BR")}
                      </p>
                    )}
                  </div>
                </section>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Reusable credential section ───────────────────────────────────────────────

interface CredentialField {
  key: string;
  label: string;
  placeholder: string;
  secret: boolean;
}

function CredentialSection({
  title, badge, docUrl, fields, form, showSecrets, set, toggleSecret,
}: {
  title: string;
  badge: string;
  docUrl: string;
  fields: CredentialField[];
  form: Record<string, string | boolean>;
  showSecrets: Record<string, boolean>;
  set: (key: string, value: string | boolean) => void;
  toggleSecret: (key: string) => void;
}) {
  return (
    <section className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
      <div className="px-6 py-4 border-b border-surface-03 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-cream">{title}</h3>
          <p className="text-stone text-sm mt-1">
            Chaves secretas são mascaradas após salvar. Deixe em branco para manter o valor atual.
          </p>
        </div>
        <a
          href={docUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-orange-400 border border-gold/40 px-3 py-1.5 rounded-lg hover:bg-gold/10 transition-colors flex-shrink-0"
        >
          Documentação ↗
        </a>
      </div>
      <div className="p-6 space-y-4">
        {fields.map(({ key, label, placeholder, secret }) => (
          <div key={key}>
            <label className="block text-parchment text-sm font-medium mb-2">{label}</label>
            <div className="flex items-center gap-2 bg-surface-03 border border-surface-03 rounded-lg px-4 py-2 focus-within:border-gold transition-colors">
              <input
                type={secret && !showSecrets[key] ? "password" : "text"}
                value={(form[key] as string) || ""}
                onChange={(e) => set(key, e.target.value)}
                placeholder={placeholder}
                autoComplete="off"
                className="flex-1 bg-transparent text-cream placeholder-slate-500 outline-none text-sm font-mono"
              />
              {secret && (
                <button
                  type="button"
                  onClick={() => toggleSecret(key)}
                  className="text-stone hover:text-cream transition-colors flex-shrink-0"
                >
                  {showSecrets[key] ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
