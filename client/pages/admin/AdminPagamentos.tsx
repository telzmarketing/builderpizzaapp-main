import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Banknote,
  CheckCircle,
  Copy,
  CreditCard,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  QrCode,
  Route,
  Save,
  ShieldCheck,
  TestTube2,
  Wallet,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  adminApi,
  type ApiPaymentGatewayConfig,
  type ApiPaymentGatewayConfigUpdate,
} from "@/lib/api";

type Provider = "mercado_pago" | "asaas";

type FormState = Record<string, string | boolean | number>;

const inputClass =
  "w-full rounded-lg border border-surface-03 bg-surface-03 px-4 py-2.5 text-sm text-cream placeholder-stone outline-none transition-colors focus:border-gold";

const providerLabels: Record<Provider, string> = {
  mercado_pago: "Mercado Pago",
  asaas: "ASAAS",
};

const asaasCardSafetyReason =
  "Ative ASAAS, Cartao ASAAS e uma API Key para rotear cartao pelo ASAAS.";

function bool(value: unknown) {
  return value === true;
}

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

function numberValue(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function formatDate(value?: string | null) {
  if (!value) return "Nunca testado";
  return new Date(value).toLocaleString("pt-BR");
}

function masked(value?: string | null) {
  return value || "Nao configurado";
}

export default function AdminPagamentos() {
  const [config, setConfig] = useState<ApiPaymentGatewayConfig | null>(null);
  const [form, setForm] = useState<FormState>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testingProvider, setTestingProvider] = useState<Provider | null>(null);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  const asaasApiConfigured = Boolean(config?.asaas_api_key_masked || text(form.asaas_api_key));
  const asaasCardSelectable =
    bool(form.asaas_enabled) && bool(form.asaas_credit_card_enabled) && asaasApiConfigured;
  const mpWebhookUrl = `${window.location.origin}/api/webhooks/mercadopago`;
  const asaasWebhookUrl = `${window.location.origin}/api/webhooks/asaas`;

  const loadConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.getPaymentGateway();
      setConfig(data);
      setForm({
        accept_pix: data.accept_pix,
        accept_credit_card: data.accept_credit_card,
        accept_debit_card: data.accept_debit_card,
        accept_cash: data.accept_cash,
        pix_provider: data.pix_provider || "mercado_pago",
        credit_card_provider: data.credit_card_provider || "mercado_pago",
        mp_enabled: data.mp_enabled,
        mp_environment: data.mp_environment || "sandbox",
        mp_public_key: data.mp_public_key || "",
        mp_access_token: "",
        mp_webhook_secret: "",
        mp_pix_enabled: data.mp_pix_enabled,
        mp_credit_card_enabled: data.mp_credit_card_enabled,
        mp_max_installments: data.mp_max_installments || 6,
        asaas_enabled: data.asaas_enabled,
        asaas_environment: data.asaas_environment || "sandbox",
        asaas_api_key: "",
        asaas_webhook_token: "",
        asaas_pix_enabled: data.asaas_pix_enabled,
        asaas_credit_card_enabled: data.asaas_credit_card_enabled,
        asaas_max_installments: data.asaas_max_installments || 1,
        asaas_tokenization_status: data.asaas_tokenization_status || "not_validated",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar a configuracao.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const currentRouting = useMemo(() => ({
    pix: providerLabels[(text(form.pix_provider) as Provider) || "mercado_pago"] || text(form.pix_provider),
    card: providerLabels[(text(form.credit_card_provider) as Provider) || "mercado_pago"] || text(form.credit_card_provider),
  }), [form.pix_provider, form.credit_card_provider]);

  const set = (key: string, value: string | boolean | number) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleSecret = (key: string) => {
    setShowSecrets((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const creditCardProvider = asaasCardSelectable ? text(form.credit_card_provider) : "mercado_pago";
      const payload: ApiPaymentGatewayConfigUpdate = {
        gateway: "mercadopago",
        sandbox: text(form.mp_environment) !== "production",
        accept_pix: bool(form.accept_pix),
        accept_credit_card: bool(form.accept_credit_card),
        accept_debit_card: bool(form.accept_debit_card),
        accept_cash: bool(form.accept_cash),
        pix_provider: text(form.pix_provider) || "mercado_pago",
        credit_card_provider: creditCardProvider,
        mp_enabled: bool(form.mp_enabled),
        mp_environment: text(form.mp_environment) || "sandbox",
        mp_public_key: text(form.mp_public_key) || null,
        mp_pix_enabled: bool(form.mp_pix_enabled),
        mp_credit_card_enabled: bool(form.mp_credit_card_enabled),
        mp_max_installments: numberValue(form.mp_max_installments, 6),
        asaas_enabled: bool(form.asaas_enabled),
        asaas_environment: text(form.asaas_environment) || "sandbox",
        asaas_pix_enabled: bool(form.asaas_pix_enabled),
        asaas_credit_card_enabled: bool(form.asaas_credit_card_enabled),
        asaas_max_installments: numberValue(form.asaas_max_installments, 1),
        asaas_tokenization_status: text(form.asaas_tokenization_status) || "not_validated",
      };
      if (text(form.mp_access_token)) payload.mp_access_token = text(form.mp_access_token);
      if (text(form.mp_webhook_secret)) payload.mp_webhook_secret = text(form.mp_webhook_secret);
      if (text(form.asaas_api_key)) payload.asaas_api_key = text(form.asaas_api_key);
      if (text(form.asaas_webhook_token)) payload.asaas_webhook_token = text(form.asaas_webhook_token);

      const updated = await adminApi.updatePaymentGateway(payload);
      setConfig(updated);
      setForm((prev) => ({
        ...prev,
        mp_access_token: "",
        mp_webhook_secret: "",
        asaas_api_key: "",
        asaas_webhook_token: "",
        credit_card_provider: updated.credit_card_provider || "mercado_pago",
        asaas_credit_card_enabled: updated.asaas_credit_card_enabled,
      }));
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar configuracao.");
    } finally {
      setSaving(false);
    }
  };

  const testProvider = async (provider: Provider) => {
    setTestingProvider(provider);
    setTestMessage(null);
    setError(null);
    try {
      const result = await adminApi.testPaymentGatewayProvider(provider);
      setTestMessage(`${providerLabels[provider]}: ${result.message}`);
      await loadConfig();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel testar o gateway.");
    } finally {
      setTestingProvider(null);
    }
  };

  return (
    <div className="min-h-screen bg-surface-00">
      <div className="flex min-h-screen flex-col md:flex-row md:h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="sticky top-0 z-20 flex items-center justify-between border-b border-surface-03 bg-surface-02 px-8 py-4">
            <div>
              <h2 className="text-2xl font-bold text-cream">Pagamentos</h2>
              <p className="mt-0.5 text-sm text-stone">Roteamento e credenciais dos gateways de pagamento</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={save}
                disabled={saving || loading}
                className="flex items-center gap-2 rounded-lg bg-gold px-5 py-2 font-bold text-cream transition-colors hover:bg-gold/90 disabled:opacity-50"
              >
                {saving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                {saving ? "Salvando..." : "Salvar"}
              </button>
              <AdminTopActions />
            </div>
          </div>

          <main className="space-y-6 p-8">
            {error && (
              <StatusBanner tone="error" icon={AlertCircle} text={error} />
            )}
            {saved && (
              <StatusBanner tone="success" icon={CheckCircle} text="Configuracao salva com sucesso." />
            )}
            {testMessage && (
              <StatusBanner tone="info" icon={TestTube2} text={testMessage} />
            )}

            {loading ? (
              <div className="flex items-center justify-center py-24">
                <Loader2 size={40} className="animate-spin text-gold" />
              </div>
            ) : (
              <>
                <section className="rounded-lg border border-surface-03 bg-surface-02">
                  <SectionHeader
                    icon={Route}
                    title="Roteamento"
                    description="Define qual gateway sera usado para novos pagamentos. Pedidos ja criados permanecem no provider historico."
                  />
                  <div className="grid gap-5 p-6 lg:grid-cols-2">
                    <RoutingControl
                      title="Gateway do Pix"
                      value={text(form.pix_provider) as Provider}
                      onChange={(provider) => set("pix_provider", provider)}
                      options={[
                        { provider: "mercado_pago", enabled: true },
                        { provider: "asaas", enabled: true },
                      ]}
                    />
                    <RoutingControl
                      title="Gateway do cartao"
                      value={text(form.credit_card_provider) as Provider}
                      onChange={(provider) => set("credit_card_provider", provider)}
                      options={[
                        { provider: "mercado_pago", enabled: true },
                        {
                          provider: "asaas",
                          enabled: asaasCardSelectable,
                          reason: asaasCardSafetyReason,
                        },
                      ]}
                    />
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100 lg:col-span-2">
                      Sem fallback automatico: se o gateway escolhido estiver indisponivel, o checkout retornara erro em vez de trocar de provedor sozinho.
                    </div>
                    <div className="rounded-lg border border-surface-03 bg-surface-03 px-4 py-3 text-sm text-parchment lg:col-span-2">
                      Rotas atuais: Pix via <strong>{currentRouting.pix}</strong>; cartao via <strong>{currentRouting.card}</strong>.
                    </div>
                  </div>
                </section>

                <section className="rounded-lg border border-surface-03 bg-surface-02">
                  <SectionHeader icon={Wallet} title="Metodos aceitos" description="Controla o que o cliente pode escolher no checkout." />
                  <div className="grid gap-3 p-6 md:grid-cols-4">
                    <ToggleTile icon={QrCode} label="Pix" checked={bool(form.accept_pix)} onClick={() => set("accept_pix", !bool(form.accept_pix))} />
                    <ToggleTile icon={CreditCard} label="Credito" checked={bool(form.accept_credit_card)} onClick={() => set("accept_credit_card", !bool(form.accept_credit_card))} />
                    <ToggleTile icon={Wallet} label="Debito" checked={bool(form.accept_debit_card)} onClick={() => set("accept_debit_card", !bool(form.accept_debit_card))} />
                    <ToggleTile icon={Banknote} label="Na entrega" checked={bool(form.accept_cash)} onClick={() => set("accept_cash", !bool(form.accept_cash))} />
                  </div>
                </section>

                <ProviderSection
                  provider="mercado_pago"
                  title="Mercado Pago"
                  enabled={bool(form.mp_enabled)}
                  onEnabledChange={(value) => set("mp_enabled", value)}
                  environment={text(form.mp_environment)}
                  onEnvironmentChange={(value) => set("mp_environment", value)}
                  healthStatus={config?.mp_last_health_check_status}
                  healthMessage={config?.mp_last_health_check_message}
                  lastCheck={config?.mp_last_health_check_at}
                  testing={testingProvider === "mercado_pago"}
                  onTest={() => testProvider("mercado_pago")}
                  webhookUrl={mpWebhookUrl}
                >
                  <div className="grid gap-4 lg:grid-cols-2">
                    <Field label="Public Key">
                      <input className={inputClass} value={text(form.mp_public_key)} onChange={(e) => set("mp_public_key", e.target.value)} placeholder="APP_USR-..." />
                    </Field>
                    <SecretField
                      label="Access Token"
                      fieldKey="mp_access_token"
                      value={text(form.mp_access_token)}
                      placeholder={masked(config?.mp_access_token_masked)}
                      show={!!showSecrets.mp_access_token}
                      onToggle={() => toggleSecret("mp_access_token")}
                      onChange={(value) => set("mp_access_token", value)}
                    />
                    <SecretField
                      label="Webhook Secret"
                      fieldKey="mp_webhook_secret"
                      value={text(form.mp_webhook_secret)}
                      placeholder={masked(config?.mp_webhook_secret_masked)}
                      show={!!showSecrets.mp_webhook_secret}
                      onToggle={() => toggleSecret("mp_webhook_secret")}
                      onChange={(value) => set("mp_webhook_secret", value)}
                    />
                    <Field label="Maximo de parcelas">
                      <input
                        type="number"
                        min={1}
                        max={12}
                        className={inputClass}
                        value={numberValue(form.mp_max_installments, 6)}
                        onChange={(e) => set("mp_max_installments", Number(e.target.value))}
                      />
                    </Field>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <InlineToggle label="Pix Mercado Pago" checked={bool(form.mp_pix_enabled)} onChange={() => set("mp_pix_enabled", !bool(form.mp_pix_enabled))} />
                    <InlineToggle label="Cartao Mercado Pago" checked={bool(form.mp_credit_card_enabled)} onChange={() => set("mp_credit_card_enabled", !bool(form.mp_credit_card_enabled))} />
                  </div>
                </ProviderSection>

                <ProviderSection
                  provider="asaas"
                  title="ASAAS"
                  enabled={bool(form.asaas_enabled)}
                  onEnabledChange={(value) => set("asaas_enabled", value)}
                  environment={text(form.asaas_environment)}
                  onEnvironmentChange={(value) => set("asaas_environment", value)}
                  healthStatus={config?.asaas_last_health_check_status}
                  healthMessage={config?.asaas_last_health_check_message}
                  lastCheck={config?.asaas_last_health_check_at}
                  testing={testingProvider === "asaas"}
                  onTest={() => testProvider("asaas")}
                  webhookUrl={asaasWebhookUrl}
                >
                  <div className="grid gap-4 lg:grid-cols-2">
                    <SecretField
                      label="API Key"
                      fieldKey="asaas_api_key"
                      value={text(form.asaas_api_key)}
                      placeholder={masked(config?.asaas_api_key_masked)}
                      show={!!showSecrets.asaas_api_key}
                      onToggle={() => toggleSecret("asaas_api_key")}
                      onChange={(value) => set("asaas_api_key", value)}
                    />
                    <SecretField
                      label="Token do webhook"
                      fieldKey="asaas_webhook_token"
                      value={text(form.asaas_webhook_token)}
                      placeholder={masked(config?.asaas_webhook_token_masked)}
                      show={!!showSecrets.asaas_webhook_token}
                      onToggle={() => toggleSecret("asaas_webhook_token")}
                      onChange={(value) => set("asaas_webhook_token", value)}
                    />
                    <Field label="Status operacional do cartao">
                      <select className={inputClass} value={text(form.asaas_tokenization_status)} onChange={(e) => set("asaas_tokenization_status", e.target.value)}>
                        <option value="not_validated">Nao validada</option>
                        <option value="unavailable">Indisponivel</option>
                        <option value="pending">Em validacao</option>
                        <option value="validated">Validada</option>
                      </select>
                    </Field>
                    <Field label="Maximo de parcelas">
                      <input
                        type="number"
                        min={1}
                        max={12}
                        className={inputClass}
                        value={numberValue(form.asaas_max_installments, 1)}
                        onChange={(e) => set("asaas_max_installments", Number(e.target.value))}
                      />
                    </Field>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <InlineToggle label="Pix ASAAS" checked={bool(form.asaas_pix_enabled)} onChange={() => set("asaas_pix_enabled", !bool(form.asaas_pix_enabled))} />
                    <InlineToggle
                      label="Cartao ASAAS"
                      checked={bool(form.asaas_credit_card_enabled)}
                      onChange={() => set("asaas_credit_card_enabled", !bool(form.asaas_credit_card_enabled))}
                    />
                  </div>
                  <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">
                    Cartao ASAAS usa o checkout seguro da loja: os dados sao enviados somente para processar a compra e nao ficam salvos no sistema.
                  </div>
                  {!asaasCardSelectable && (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                      {asaasCardSafetyReason}
                    </div>
                  )}
                </ProviderSection>
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

function StatusBanner({ tone, icon: Icon, text }: { tone: "error" | "success" | "info"; icon: typeof AlertCircle; text: string }) {
  const styles = {
    error: "border-red-500/40 bg-red-500/10 text-red-300",
    success: "border-green-500/40 bg-green-500/10 text-green-300",
    info: "border-blue-500/40 bg-blue-500/10 text-blue-200",
  };
  return (
    <div className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${styles[tone]}`}>
      <Icon size={18} />
      <span className="text-sm">{text}</span>
    </div>
  );
}

function SectionHeader({ icon: Icon, title, description }: { icon: typeof Route; title: string; description: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-surface-03 px-6 py-4">
      <Icon size={20} className="mt-0.5 text-gold" />
      <div>
        <h3 className="text-lg font-bold text-cream">{title}</h3>
        <p className="mt-1 text-sm text-stone">{description}</p>
      </div>
    </div>
  );
}

function RoutingControl({
  title,
  value,
  onChange,
  options,
}: {
  title: string;
  value: Provider;
  onChange: (provider: Provider) => void;
  options: { provider: Provider; enabled: boolean; reason?: string }[];
}) {
  return (
    <div>
      <p className="mb-2 text-sm font-semibold text-parchment">{title}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((option) => (
          <button
            key={option.provider}
            type="button"
            disabled={!option.enabled}
            onClick={() => onChange(option.provider)}
            className={`rounded-lg border px-4 py-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              value === option.provider ? "border-gold bg-gold/10 text-gold-light" : "border-surface-03 bg-surface-03 text-stone hover:border-brand-mid"
            }`}
          >
            <span className="block text-sm font-bold">{providerLabels[option.provider]}</span>
            <span className="block text-xs opacity-80">{option.enabled ? "Disponivel para selecao" : option.reason}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ToggleTile({ icon: Icon, label, checked, onClick }: { icon: typeof QrCode; label: string; checked: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors ${
        checked ? "border-gold bg-gold/10 text-gold-light" : "border-surface-03 bg-surface-03 text-stone hover:border-brand-mid"
      }`}
    >
      <Icon size={22} />
      <span className="text-center text-sm font-semibold">{label}</span>
    </button>
  );
}

function ProviderSection({
  provider,
  title,
  enabled,
  onEnabledChange,
  environment,
  onEnvironmentChange,
  healthStatus,
  healthMessage,
  lastCheck,
  testing,
  onTest,
  webhookUrl,
  children,
}: {
  provider: Provider;
  title: string;
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  environment: string;
  onEnvironmentChange: (value: string) => void;
  healthStatus?: string | null;
  healthMessage?: string | null;
  lastCheck?: string | null;
  testing: boolean;
  onTest: () => void;
  webhookUrl: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-surface-03 bg-surface-02">
      <div className="flex flex-col gap-4 border-b border-surface-03 px-6 py-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          {provider === "mercado_pago" ? <ShieldCheck size={20} className="mt-0.5 text-gold" /> : <KeyRound size={20} className="mt-0.5 text-gold" />}
          <div>
            <h3 className="text-lg font-bold text-cream">{title}</h3>
            <p className="mt-1 text-sm text-stone">Ambiente, credenciais, metodos e webhook do provider.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onEnabledChange(!enabled)}
            className={`rounded-lg border px-3 py-2 text-xs font-bold transition-colors ${
              enabled ? "border-green-500/50 bg-green-500/10 text-green-300" : "border-surface-03 bg-surface-03 text-stone"
            }`}
          >
            {enabled ? "Ativo" : "Inativo"}
          </button>
          <button
            type="button"
            onClick={onTest}
            disabled={testing}
            className="flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-03 px-3 py-2 text-xs font-bold text-parchment transition-colors hover:border-gold disabled:opacity-50"
          >
            {testing ? <Loader2 size={14} className="animate-spin" /> : <TestTube2 size={14} />}
            Testar conexao
          </button>
        </div>
      </div>
      <div className="space-y-5 p-6">
        <div className="grid gap-4 lg:grid-cols-3">
          <Field label="Ambiente">
            <select className={inputClass} value={environment} onChange={(e) => onEnvironmentChange(e.target.value)}>
              <option value="sandbox">Sandbox</option>
              <option value="production">Producao</option>
            </select>
          </Field>
          <InfoBlock label="Ultimo teste" value={formatDate(lastCheck)} />
          <InfoBlock label="Status" value={`${healthStatus || "not_tested"}${healthMessage ? ` - ${healthMessage}` : ""}`} />
        </div>
        {children}
        <WebhookBox url={webhookUrl} />
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-parchment">{label}</span>
      {children}
    </label>
  );
}

function SecretField({
  label,
  fieldKey,
  value,
  placeholder,
  show,
  onToggle,
  onChange,
}: {
  label: string;
  fieldKey: string;
  value: string;
  placeholder: string;
  show: boolean;
  onToggle: () => void;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <div className="flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-03 px-4 py-2.5 focus-within:border-gold">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent font-mono text-sm text-cream outline-none placeholder-stone"
          aria-label={fieldKey}
        />
        <button type="button" onClick={onToggle} className="text-stone transition-colors hover:text-cream">
          {show ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </div>
    </Field>
  );
}

function InlineToggle({
  label,
  checked,
  disabled,
  disabledText,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  disabledText?: string;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onChange}
      className={`flex items-center justify-between rounded-lg border px-4 py-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        checked ? "border-gold bg-gold/10 text-gold-light" : "border-surface-03 bg-surface-03 text-stone hover:border-brand-mid"
      }`}
    >
      <span>
        <span className="block text-sm font-bold">{label}</span>
        {disabled && disabledText && <span className="block text-xs opacity-80">{disabledText}</span>}
      </span>
      <span className={`h-3 w-3 rounded-full ${checked ? "bg-gold" : "bg-stone/40"}`} />
    </button>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-03 bg-surface-03 px-4 py-3">
      <p className="text-xs font-semibold uppercase text-stone">{label}</p>
      <p className="mt-1 break-words text-sm text-parchment">{value}</p>
    </div>
  );
}

function WebhookBox({ url }: { url: string }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-parchment">URL do webhook</p>
      <div className="flex items-center gap-2 rounded-lg border border-surface-03 bg-surface-03 px-4 py-3">
        <code className="min-w-0 flex-1 break-all text-sm text-gold">{url}</code>
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText(url)}
          className="flex items-center gap-1 rounded border border-surface-03 px-2 py-1 text-xs text-parchment transition-colors hover:border-gold"
        >
          <Copy size={13} />
          Copiar
        </button>
      </div>
    </div>
  );
}
