import { useEffect, useState } from "react";
import { Save, Zap, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { chatbotAdminApi, type ChatbotSettings } from "@/lib/chatbotApi";

const CLAUDE_MODELS = [
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5 (rápido, barato)" },
  { value: "claude-sonnet-4-6",         label: "Claude Sonnet 4.6 (balanceado)" },
  { value: "claude-opus-4-7",           label: "Claude Opus 4.7 (mais capaz)" },
];
const OPENAI_MODELS = [
  { value: "gpt-4o-mini", label: "GPT-4o Mini (rápido, barato)" },
  { value: "gpt-4o",      label: "GPT-4o (balanceado)" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo (avançado)" },
];

export default function ChatbotAI() {
  const [settings, setSettings] = useState<ChatbotSettings | null>(null);
  const [status, setStatus] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState("");
  const [testResult, setTestResult] = useState<{ resposta: string; latencia_ms: number; tokens: number } | null>(null);

  useEffect(() => {
    Promise.all([chatbotAdminApi.getSettings(), chatbotAdminApi.aiStatus()])
      .then(([s, st]) => { setSettings(s); setStatus(st); });
  }, []);

  if (!settings) return <div className="text-stone text-center py-16">Carregando...</div>;

  const upd = (k: keyof ChatbotSettings, v: unknown) =>
    setSettings((prev) => prev ? { ...prev, [k]: v } : prev);

  const models = settings.provedor_ia === "claude" ? CLAUDE_MODELS : OPENAI_MODELS;

  const save = async () => {
    setSaving(true); setMsg("");
    try {
      const s = await chatbotAdminApi.updateSettings({
        provedor_ia: settings.provedor_ia,
        modelo_ia:   settings.modelo_ia,
        temperatura: settings.temperatura,
        max_tokens:  settings.max_tokens,
      });
      setSettings(s); setMsg("Salvo!");
      const st = await chatbotAdminApi.aiStatus();
      setStatus(st);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erro.");
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setTestResult(null); setMsg("");
    try {
      const r = await chatbotAdminApi.testAI();
      setTestResult(r);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erro no teste.");
    } finally { setTesting(false); }
  };

  const isConfigured = status[settings.provedor_ia] === true;

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

      {/* Status badges */}
      <div className="flex gap-3 flex-wrap">
        {[
          { key: "claude", label: "Claude (Anthropic)" },
          { key: "openai", label: "OpenAI" },
        ].map(({ key, label }) => (
          <div key={key} className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium ${
            status[key] ? "bg-green-500/10 border-green-500/30 text-green-400" : "bg-surface-03 border-surface-03 text-stone"
          }`}>
            {status[key] ? <CheckCircle size={13} /> : <XCircle size={13} />}
            {label}
            {status[key] ? " — Configurado" : " — Sem chave"}
          </div>
        ))}
      </div>

      {!isConfigured && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl px-4 py-3 text-orange-300 text-sm">
          O provedor selecionado não possui chave de API configurada no servidor. Configure a variável <code className="bg-surface-03 px-1 rounded text-xs">{settings.provedor_ia === "claude" ? "ANTHROPIC_API_KEY" : "OPENAI_API_KEY"}</code> no arquivo <code className="bg-surface-03 px-1 rounded text-xs">.env</code> do backend.
        </div>
      )}

      {/* Provedor */}
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

      {/* Modelo */}
      <div>
        <label className="block text-parchment text-xs font-medium mb-1">Modelo</label>
        <select value={settings.modelo_ia} onChange={(e) => upd("modelo_ia", e.target.value)}
          className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold">
          {models.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>

      {/* Temperatura */}
      <div>
        <label className="block text-parchment text-xs font-medium mb-1">
          Temperatura — <span className="text-gold">{settings.temperatura.toFixed(1)}</span>
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

      {/* Max tokens */}
      <div>
        <label className="block text-parchment text-xs font-medium mb-1">Máximo de tokens por resposta</label>
        <input type="number" min={100} max={4096} step={50}
          value={settings.max_tokens}
          onChange={(e) => upd("max_tokens", Number(e.target.value))}
          className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
        />
        <p className="text-stone text-xs mt-1">Recomendado: 512–1024 para chatbot de atendimento.</p>
      </div>

      {/* Test */}
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
