import { useEffect, useState } from "react";
import { Save, Zap, CheckCircle, XCircle, Loader2, KeyRound } from "lucide-react";
import { chatbotAdminApi, type ChatbotAIStatus, type ChatbotSettings } from "@/lib/chatbotApi";

const CLAUDE_MODELS = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4 (balanceado)" },
  { value: "claude-3-5-haiku-20241022", label: "Claude Haiku 3.5 (rápido, barato)" },
  { value: "claude-opus-4-1-20250805", label: "Claude Opus 4.1 (mais capaz)" },
];

const OPENAI_MODELS = [
  { value: "gpt-4o-mini", label: "GPT-4o Mini (rápido, barato)" },
  { value: "gpt-4o", label: "GPT-4o (balanceado)" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo (avançado)" },
];

const EMPTY_STATUS: ChatbotAIStatus = {
  claude: false,
  openai: false,
  ativo: false,
  using_fallback_provider: false,
  openai_key_preview: null,
  anthropic_key_preview: null,
};

export default function ChatbotAI() {
  const [settings, setSettings] = useState<ChatbotSettings | null>(null);
  const [status, setStatus] = useState<ChatbotAIStatus>(EMPTY_STATUS);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [savingKeys, setSavingKeys] = useState(false);
  const [msg, setMsg] = useState("");
  const [openAIKey, setOpenAIKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [testResult, setTestResult] = useState<{ resposta: string; latencia_ms: number; tokens: number } | null>(null);

  useEffect(() => {
    Promise.all([chatbotAdminApi.getSettings(), chatbotAdminApi.aiStatus()])
      .then(([s, st]) => { setSettings(s); setStatus(st); });
  }, []);

  if (!settings) return <div className="text-stone text-center py-16">Carregando...</div>;

  const upd = (k: keyof ChatbotSettings, v: unknown) =>
    setSettings((prev) => prev ? { ...prev, [k]: v } : prev);

  const models = settings.provedor_ia === "claude" ? CLAUDE_MODELS : OPENAI_MODELS;
  const modelValue = models.some((m) => m.value === settings.modelo_ia)
    ? settings.modelo_ia
    : models[0].value;

  const save = async () => {
    setSaving(true); setMsg("");
    try {
      const s = await chatbotAdminApi.updateSettings({
        provedor_ia: settings.provedor_ia,
        modelo_ia: modelValue,
        temperatura: settings.temperatura,
        max_tokens: settings.max_tokens,
      });
      setSettings(s); setMsg("Salvo!");
      setStatus(await chatbotAdminApi.aiStatus());
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erro.");
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setTestResult(null); setMsg("");
    try {
      setTestResult(await chatbotAdminApi.testAI());
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erro no teste.");
    } finally { setTesting(false); }
  };

  const saveKeys = async () => {
    const body: { openai_api_key?: string; anthropic_api_key?: string } = {};
    if (openAIKey.trim()) body.openai_api_key = openAIKey.trim();
    if (anthropicKey.trim()) body.anthropic_api_key = anthropicKey.trim();

    if (!body.openai_api_key && !body.anthropic_api_key) {
      setMsg("Informe pelo menos uma chave.");
      return;
    }

    setSavingKeys(true); setMsg("");
    try {
      setStatus(await chatbotAdminApi.updateAIKeys(body));
      setOpenAIKey("");
      setAnthropicKey("");
      setMsg("Chaves salvas!");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erro ao salvar chaves.");
    } finally { setSavingKeys(false); }
  };

  const selectedConfigured = status[settings.provedor_ia] === true;
  const isConfigured = status.ativo === true;
  const usingFallbackProvider = status.using_fallback_provider === true;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-cream font-bold text-base">Provedor de IA</h3>
        <div className="flex items-center gap-3">
          {msg && <span className={msg.includes("Erro") ? "text-red-400 text-xs" : "text-green-400 text-xs"}>{msg}</span>}
          <button onClick={save} disabled={saving}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
            <Save size={14} /> {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap">
        {[
          { key: "claude" as const, label: "Claude (Anthropic)", preview: status.anthropic_key_preview },
          { key: "openai" as const, label: "OpenAI", preview: status.openai_key_preview },
        ].map(({ key, label, preview }) => (
          <div key={key} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium ${
            status[key] ? "bg-green-500/10 border-green-500/30 text-green-400" : "bg-surface-03 border-surface-03 text-stone"
          }`}>
            {status[key] ? <CheckCircle size={13} /> : <XCircle size={13} />}
            {label}
            {status[key] ? ` - Configurado${preview ? ` (${preview})` : ""}` : " - Sem chave"}
          </div>
        ))}
      </div>

      {!selectedConfigured && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl px-4 py-3 text-orange-300 text-sm">
          {usingFallbackProvider
            ? "O provedor selecionado não possui chave no servidor; o backend usará o outro provedor configurado."
            : <>O provedor selecionado não possui chave de API configurada no servidor. Configure a variável <code className="bg-surface-03 px-1 rounded text-xs">{settings.provedor_ia === "claude" ? "ANTHROPIC_API_KEY" : "OPENAI_API_KEY"}</code> no arquivo <code className="bg-surface-03 px-1 rounded text-xs">backend/.env</code> ou pelo campo abaixo.</>}
        </div>
      )}

      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-parchment text-sm font-medium flex items-center gap-2">
            <KeyRound size={14} className="text-gold" /> Chaves dos provedores
          </span>
          <button onClick={saveKeys} disabled={savingKeys}
            className="flex items-center gap-2 bg-surface-03 hover:bg-surface-02 disabled:opacity-50 border border-surface-03 text-parchment py-1.5 px-4 rounded-lg text-xs font-medium transition-colors">
            <Save size={13} /> {savingKeys ? "Salvando..." : "Salvar chaves"}
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="block text-parchment text-xs font-medium mb-1">OpenAI API key</span>
            <input
              type="password"
              value={openAIKey}
              onChange={(e) => setOpenAIKey(e.target.value)}
              placeholder={status.openai_key_preview ? `${status.openai_key_preview} - deixe vazio para manter` : "sk-..."}
              autoComplete="off"
              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
            />
          </label>

          <label className="block">
            <span className="block text-parchment text-xs font-medium mb-1">Claude API key</span>
            <input
              type="password"
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder={status.anthropic_key_preview ? `${status.anthropic_key_preview} - deixe vazio para manter` : "sk-ant-..."}
              autoComplete="off"
              className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
            />
          </label>
        </div>

        <p className="text-stone text-xs">
          As chaves são salvas no banco de dados e no backend/.env. Por segurança, o painel mostra apenas uma prévia mascarada.
        </p>
      </div>

      <div>
        <label className="block text-parchment text-xs font-medium mb-2">Provedor</label>
        <div className="flex gap-3">
          {(["claude", "openai"] as const).map((p) => (
            <button key={p} onClick={() => {
              upd("provedor_ia", p);
              upd("modelo_ia", p === "claude" ? CLAUDE_MODELS[0].value : OPENAI_MODELS[0].value);
            }}
              className={`flex-1 py-3 rounded-xl border text-sm font-medium transition-colors ${
                settings.provedor_ia === p
                  ? "bg-gold/20 border-gold text-gold"
                  : "bg-surface-03 border-surface-03 text-stone hover:text-parchment"
              }`}
            >
              {p === "claude" ? "Claude (Anthropic)" : "OpenAI (GPT)"}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-parchment text-xs font-medium mb-1">Modelo</label>
        <select value={modelValue} onChange={(e) => upd("modelo_ia", e.target.value)}
          className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold">
          {models.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>

      <div>
        <label className="block text-parchment text-xs font-medium mb-1">
          Temperatura - <span className="text-gold">{settings.temperatura.toFixed(1)}</span>
          <span className="text-stone ml-2 font-normal">(0 = determinístico, 1 = criativo)</span>
        </label>
        <input type="range" min={0} max={1} step={0.1}
          value={settings.temperatura}
          onChange={(e) => upd("temperatura", parseFloat(e.target.value))}
          className="w-full accent-gold"
        />
        <div className="flex justify-between text-stone text-xs mt-0.5">
          <span>0.0</span><span>0.5</span><span>1.0</span>
        </div>
      </div>

      <div>
        <label className="block text-parchment text-xs font-medium mb-1">Máximo de tokens por resposta</label>
        <input type="number" min={100} max={4096} step={50}
          value={settings.max_tokens}
          onChange={(e) => upd("max_tokens", Number(e.target.value))}
          className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
        />
        <p className="text-stone text-xs mt-1">Recomendado: 512-1024 para chatbot de atendimento.</p>
      </div>

      <div className="bg-surface-02 border border-surface-03 rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-parchment text-sm font-medium">Testar conexão com IA</span>
          <button onClick={test} disabled={testing || !isConfigured}
            className="flex items-center gap-2 bg-surface-03 hover:bg-surface-02 disabled:opacity-50 border border-surface-03 text-parchment py-1.5 px-4 rounded-lg text-xs font-medium transition-colors">
            {testing ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} className="text-gold" />}
            {testing ? "Testando..." : "Testar agora"}
          </button>
        </div>

        {testResult && (
          <div className="space-y-2">
            <div className="bg-surface-03 rounded-lg px-3 py-2 text-parchment text-sm">{testResult.resposta}</div>
            <div className="flex gap-4 text-stone text-xs">
              <span>Latência: <span className="text-parchment">{testResult.latencia_ms}ms</span></span>
              <span>Tokens: <span className="text-parchment">{testResult.tokens}</span></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
