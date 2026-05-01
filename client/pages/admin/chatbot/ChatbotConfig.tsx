import { useEffect, useState, useRef } from "react";
import {
  Save, Eye, Zap, CheckCircle, XCircle, Loader2, KeyRound,
  Brain, Play, X, ChevronDown, ChevronRight, Cpu, Settings2,
} from "lucide-react";
import {
  chatbotAdminApi, chatbotPublicApi,
  type ChatbotSettings, type ChatbotAIStatus,
} from "@/lib/chatbotApi";

// ─── AI model lists ───────────────────────────────────────────────────────────

const CLAUDE_MODELS = [
  { value: "claude-sonnet-4-20250514",  label: "Claude Sonnet 4 (balanceado)" },
  { value: "claude-3-5-haiku-20241022", label: "Claude Haiku 3.5 (rápido)" },
  { value: "claude-opus-4-1-20250805",  label: "Claude Opus 4.1 (mais capaz)" },
];
const OPENAI_MODELS = [
  { value: "gpt-4o-mini",  label: "GPT-4o Mini (rápido, barato)" },
  { value: "gpt-4o",       label: "GPT-4o (balanceado)" },
  { value: "gpt-4-turbo",  label: "GPT-4 Turbo (avançado)" },
];

const EMPTY_STATUS: ChatbotAIStatus = {
  claude: false, openai: false, ativo: false,
  using_fallback_provider: false, openai_key_preview: null, anthropic_key_preview: null,
};

// ─── Shared primitives ────────────────────────────────────────────────────────

const Toggle = ({ value, onChange }: { value: boolean; onChange: () => void }) => (
  <button
    onClick={onChange}
    className={`relative w-11 h-6 rounded-full transition-colors flex-shrink-0 ${value ? "bg-gold" : "bg-surface-03"}`}
  >
    <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${value ? "translate-x-6" : "translate-x-1"}`} />
  </button>
);

function FieldLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="mb-1.5">
      <label className="block text-parchment text-xs font-medium">{children}</label>
      {hint && <p className="text-stone text-xs mt-0.5">{hint}</p>}
    </div>
  );
}

const Inp = ({
  label, hint, ...p
}: { label?: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) => (
  <div>
    {label && <FieldLabel hint={hint}>{label}</FieldLabel>}
    <input
      {...p}
      className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold"
    />
  </div>
);

const Txt = ({
  label, hint, ...p
}: { label?: string; hint?: string } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <div>
    {label && <FieldLabel hint={hint}>{label}</FieldLabel>}
    <textarea
      {...p}
      className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold resize-none"
    />
  </div>
);

const Sel = ({
  label, children, ...p
}: { label?: string; children: React.ReactNode } & React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <div>
    {label && <FieldLabel>{label}</FieldLabel>}
    <select
      {...p}
      className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
    >
      {children}
    </select>
  </div>
);

// ─── Accordion section ────────────────────────────────────────────────────────

function Section({
  icon, title, subtitle, defaultOpen = false, children,
}: {
  icon: React.ReactNode; title: string; subtitle: string;
  defaultOpen?: boolean; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-5 py-4 flex items-center gap-4 hover:bg-surface-03/40 transition-colors text-left"
      >
        <span className="text-gold flex-shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-cream font-bold text-sm">{title}</p>
          <p className="text-stone text-xs mt-0.5">{subtitle}</p>
        </div>
        {open
          ? <ChevronDown size={16} className="text-stone flex-shrink-0" />
          : <ChevronRight size={16} className="text-stone flex-shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-6 pt-2 border-t border-surface-03 space-y-4">
          {children}
        </div>
      )}
    </div>
  );
}

// ─── Save bar ─────────────────────────────────────────────────────────────────

function SaveBar({
  saving, msg, onSave, label = "Salvar",
}: { saving: boolean; msg: string; onSave: () => void; label?: string }) {
  const isErr = msg.toLowerCase().includes("erro") || msg.includes("Informe");
  return (
    <div className="flex items-center gap-3 pt-1">
      <button
        onClick={onSave}
        disabled={saving}
        className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 px-5 rounded-lg text-sm transition-colors"
      >
        <Save size={14} /> {saving ? "Salvando..." : label}
      </button>
      {msg && (
        <span className={`text-xs ${isErr ? "text-red-400" : "text-green-400"}`}>{msg}</span>
      )}
    </div>
  );
}

// ─── Widget preview ───────────────────────────────────────────────────────────

function WidgetPreview({ s }: { s: ChatbotSettings }) {
  const isRight = s.posicao_widget !== "bottom-left";
  return (
    <div className="relative bg-surface-03 rounded-xl h-52 border border-surface-03 overflow-hidden select-none">
      <p className="absolute top-3 left-3 text-stone text-[10px]">Preview</p>
      <div className={`absolute bottom-14 ${isRight ? "right-3" : "left-3"} w-48 bg-[#1a1a1a] rounded-xl border border-white/10 shadow-xl`}>
        <div
          className="px-3 py-2 rounded-t-xl text-white text-xs font-bold flex items-center gap-2"
          style={{ background: s.cor_primaria }}
        >
          💬 {s.nome_bot || "Bot"}
        </div>
        <div className="p-3">
          <div className="bg-[#2a2a2a] rounded-lg px-3 py-2 text-[#ccc] text-xs leading-relaxed">
            {s.mensagem_inicial || "Olá! Como posso ajudar?"}
          </div>
        </div>
      </div>
      <div
        className={`absolute bottom-3 ${isRight ? "right-3" : "left-3"} w-10 h-10 rounded-full flex items-center justify-center text-white shadow-lg text-lg`}
        style={{ background: s.cor_primaria }}
      >
        💬
      </div>
    </div>
  );
}

// ─── Prompt simulator ─────────────────────────────────────────────────────────

interface SimMsg { role: "user" | "bot"; content: string }

function Simulator({ settings }: { settings: ChatbotSettings }) {
  const [open, setOpen]   = useState(false);
  const [msgs, setMsgs]   = useState<SimMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `sim-${Date.now()}`);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", content: text }]);
    setLoading(true);
    try {
      const r = await chatbotPublicApi.message({ session_id: sessionId, mensagem: text });
      setMsgs((m) => [...m, { role: "bot", content: r.resposta || "(sem resposta)" }]);
    } catch (e: unknown) {
      setMsgs((m) => [...m, { role: "bot", content: `Erro: ${e instanceof Error ? e.message : "desconhecido"}` }]);
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 bg-surface-03 hover:bg-surface-02 border border-surface-03 text-parchment font-medium py-2 px-4 rounded-lg text-sm transition-colors"
      >
        <Play size={14} className="text-gold" /> Testar prompt no simulador
      </button>
    );
  }

  return (
    <div className="bg-surface-03 border border-gold/30 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-03/50">
        <span className="text-cream text-sm font-bold">Simulador — {settings.nome_bot}</span>
        <button onClick={() => { setOpen(false); setMsgs([]); }} className="text-stone hover:text-cream transition-colors">
          <X size={16} />
        </button>
      </div>
      <div className="h-56 overflow-y-auto p-4 space-y-3">
        {msgs.length === 0 && (
          <p className="text-stone text-xs text-center pt-8">Salve o prompt e envie uma mensagem para testar.</p>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] px-3 py-2 rounded-xl text-sm leading-relaxed ${
              m.role === "user" ? "bg-gold/20 text-cream" : "bg-surface-02 text-parchment"
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-surface-02 px-3 py-2 rounded-xl text-stone text-xs">Digitando...</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 px-4 pb-4 pt-2 border-t border-surface-03/50">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Mensagem de teste..."
          className="flex-1 bg-surface-02 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold"
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold px-4 py-2 rounded-lg text-sm transition-colors"
        >
          →
        </button>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ChatbotConfig() {
  const [settings, setSettings] = useState<ChatbotSettings | null>(null);
  const [status, setStatus]     = useState<ChatbotAIStatus>(EMPTY_STATUS);

  const [savingWidget, setSavingWidget] = useState(false);
  const [savingAI,     setSavingAI]     = useState(false);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [savingKeys,   setSavingKeys]   = useState(false);
  const [testing,      setTesting]      = useState(false);

  const [msgWidget,  setMsgWidget]  = useState("");
  const [msgAI,      setMsgAI]      = useState("");
  const [msgPrompt,  setMsgPrompt]  = useState("");
  const [msgKeys,    setMsgKeys]    = useState("");

  const [openAIKey,    setOpenAIKey]    = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [testResult,   setTestResult]   = useState<{ resposta: string; latencia_ms: number; tokens: number } | null>(null);

  useEffect(() => {
    Promise.all([chatbotAdminApi.getSettings(), chatbotAdminApi.aiStatus()])
      .then(([s, st]) => { setSettings(s); setStatus(st); });
  }, []);

  if (!settings) return <div className="text-stone text-center py-16">Carregando...</div>;

  const upd = (k: keyof ChatbotSettings, v: unknown) =>
    setSettings((prev) => prev ? { ...prev, [k]: v } : prev);

  const models     = settings.provedor_ia === "claude" ? CLAUDE_MODELS : OPENAI_MODELS;
  const modelValue = models.some((m) => m.value === settings.modelo_ia)
    ? settings.modelo_ia
    : models[0].value;

  const saveWidget = async () => {
    setSavingWidget(true); setMsgWidget("");
    try {
      const s = await chatbotAdminApi.updateSettings({
        ativo:                 settings.ativo,
        nome_bot:              settings.nome_bot,
        mensagem_inicial:      settings.mensagem_inicial,
        cor_primaria:          settings.cor_primaria,
        posicao_widget:        settings.posicao_widget,
        tempo_disparo_auto:    settings.tempo_disparo_auto,
        fallback_humano_ativo: settings.fallback_humano_ativo,
        mensagem_fora_horario: settings.mensagem_fora_horario,
        horario_funcionamento: settings.horario_funcionamento,
      });
      setSettings(s); setMsgWidget("Salvo!");
    } catch (e: unknown) { setMsgWidget(e instanceof Error ? e.message : "Erro."); }
    finally { setSavingWidget(false); }
  };

  const saveAI = async () => {
    setSavingAI(true); setMsgAI("");
    try {
      const s = await chatbotAdminApi.updateSettings({
        provedor_ia: settings.provedor_ia,
        modelo_ia:   modelValue,
        temperatura: settings.temperatura,
        max_tokens:  settings.max_tokens,
      });
      setSettings(s); setMsgAI("Salvo!");
      setStatus(await chatbotAdminApi.aiStatus());
    } catch (e: unknown) { setMsgAI(e instanceof Error ? e.message : "Erro."); }
    finally { setSavingAI(false); }
  };

  const saveKeys = async () => {
    const body: { openai_api_key?: string; anthropic_api_key?: string } = {};
    if (openAIKey.trim())    body.openai_api_key    = openAIKey.trim();
    if (anthropicKey.trim()) body.anthropic_api_key = anthropicKey.trim();
    if (!body.openai_api_key && !body.anthropic_api_key) {
      setMsgKeys("Informe pelo menos uma chave."); return;
    }
    setSavingKeys(true); setMsgKeys("");
    try {
      setStatus(await chatbotAdminApi.updateAIKeys(body));
      setOpenAIKey(""); setAnthropicKey("");
      setMsgKeys("Chaves salvas!");
    } catch (e: unknown) { setMsgKeys(e instanceof Error ? e.message : "Erro ao salvar chaves."); }
    finally { setSavingKeys(false); }
  };

  const savePrompt = async () => {
    setSavingPrompt(true); setMsgPrompt("");
    try {
      const s = await chatbotAdminApi.updateSettings({
        prompt_base:              settings.prompt_base,
        regras_fixas:             settings.regras_fixas,
        tom_de_voz:               settings.tom_de_voz,
        objetivo:                 settings.objetivo,
        instrucoes_transferencia: settings.instrucoes_transferencia,
        limitacoes_proibicoes:    settings.limitacoes_proibicoes,
      });
      setSettings(s); setMsgPrompt("Prompt salvo!");
    } catch (e: unknown) { setMsgPrompt(e instanceof Error ? e.message : "Erro."); }
    finally { setSavingPrompt(false); }
  };

  const test = async () => {
    setTesting(true); setTestResult(null);
    try { setTestResult(await chatbotAdminApi.testAI()); }
    catch (e: unknown) { setMsgAI(e instanceof Error ? e.message : "Erro no teste."); }
    finally { setTesting(false); }
  };

  return (
    <div className="max-w-3xl space-y-3">

      {/* ── 1. Widget & Aparência ─────────────────────────────────────────────── */}
      <Section
        icon={<Settings2 size={18} />}
        title="Widget & Aparência"
        subtitle="Aparência, posição e comportamento do chat na loja"
        defaultOpen
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="flex items-center gap-3 bg-surface-03 rounded-xl px-4 py-3">
              <span className="text-parchment text-sm flex-1">Chatbot ativo</span>
              <Toggle value={settings.ativo} onChange={() => upd("ativo", !settings.ativo)} />
            </div>

            <div className="flex items-center gap-3 bg-surface-03 rounded-xl px-4 py-3">
              <span className="text-parchment text-sm flex-1">Atendimento humano (fallback)</span>
              <Toggle
                value={settings.fallback_humano_ativo}
                onChange={() => upd("fallback_humano_ativo", !settings.fallback_humano_ativo)}
              />
            </div>

            <Inp
              label="Nome do bot"
              value={settings.nome_bot}
              onChange={(e) => upd("nome_bot", e.target.value)}
              placeholder="Assistente"
            />

            <Inp
              label="Mensagem de boas-vindas"
              value={settings.mensagem_inicial}
              onChange={(e) => upd("mensagem_inicial", e.target.value)}
              placeholder="Olá! Como posso ajudar?"
            />

            <div>
              <FieldLabel>Cor primária</FieldLabel>
              <div className="flex gap-3 items-center">
                <input
                  type="color"
                  value={settings.cor_primaria}
                  onChange={(e) => upd("cor_primaria", e.target.value)}
                  className="w-10 h-10 rounded-lg border border-surface-03 bg-surface-03 cursor-pointer"
                />
                <input
                  value={settings.cor_primaria}
                  onChange={(e) => upd("cor_primaria", e.target.value)}
                  className="flex-1 bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
                />
              </div>
            </div>

            <Sel
              label="Posição do widget"
              value={settings.posicao_widget}
              onChange={(e) => upd("posicao_widget", e.target.value)}
            >
              <option value="bottom-right">Canto inferior direito</option>
              <option value="bottom-left">Canto inferior esquerdo</option>
            </Sel>

            <Inp
              label="Auto-abrir após (segundos, 0 = desativado)"
              type="number"
              min={0}
              value={settings.tempo_disparo_auto}
              onChange={(e) => upd("tempo_disparo_auto", Number(e.target.value))}
            />

            <Txt
              label="Mensagem fora do horário"
              rows={2}
              value={settings.mensagem_fora_horario}
              onChange={(e) => upd("mensagem_fora_horario", e.target.value)}
              placeholder="Estamos fora do horário de atendimento."
            />
          </div>

          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Eye size={13} className="text-stone" />
              <p className="text-stone text-xs">Preview ao vivo</p>
            </div>
            <WidgetPreview s={settings} />
            <p className="text-stone text-xs mt-2">Reflete as alterações em tempo real antes de salvar.</p>
          </div>
        </div>

        <SaveBar saving={savingWidget} msg={msgWidget} onSave={saveWidget} />
      </Section>

      {/* ── 2. Provedor de IA ─────────────────────────────────────────────────── */}
      <Section
        icon={<Cpu size={18} />}
        title="Provedor de IA"
        subtitle="Chaves de API, modelo, temperatura e teste de conexão"
      >
        <div className="flex gap-3 flex-wrap">
          {([
            { key: "claude" as const, label: "Claude (Anthropic)", preview: status.anthropic_key_preview },
            { key: "openai" as const, label: "OpenAI (GPT)",       preview: status.openai_key_preview },
          ]).map(({ key, label, preview }) => (
            <div
              key={key}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium ${
                status[key]
                  ? "bg-green-500/10 border-green-500/30 text-green-400"
                  : "bg-surface-03 border-surface-03 text-stone"
              }`}
            >
              {status[key] ? <CheckCircle size={13} /> : <XCircle size={13} />}
              {label}
              {status[key] ? (preview ? ` · ${preview}` : " · configurado") : " · sem chave"}
            </div>
          ))}
        </div>

        <div className="bg-surface-03 rounded-xl p-4 space-y-3">
          <p className="text-parchment text-xs font-medium flex items-center gap-1.5">
            <KeyRound size={13} className="text-gold" /> Chaves de API
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="block text-stone text-xs mb-1">OpenAI API key</span>
              <input
                type="password"
                value={openAIKey}
                onChange={(e) => setOpenAIKey(e.target.value)}
                placeholder={status.openai_key_preview ? `${status.openai_key_preview} — manter vazio` : "sk-..."}
                autoComplete="off"
                className="w-full bg-surface-02 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
              />
            </label>
            <label className="block">
              <span className="block text-stone text-xs mb-1">Claude (Anthropic) API key</span>
              <input
                type="password"
                value={anthropicKey}
                onChange={(e) => setAnthropicKey(e.target.value)}
                placeholder={status.anthropic_key_preview ? `${status.anthropic_key_preview} — manter vazio` : "sk-ant-..."}
                autoComplete="off"
                className="w-full bg-surface-02 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold"
              />
            </label>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={saveKeys}
              disabled={savingKeys}
              className="flex items-center gap-1.5 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-1.5 px-4 rounded-lg text-xs transition-colors"
            >
              <Save size={12} /> {savingKeys ? "Salvando..." : "Salvar chaves"}
            </button>
            {msgKeys && (
              <span className={`text-xs ${msgKeys.toLowerCase().includes("erro") || msgKeys.includes("Informe") ? "text-red-400" : "text-green-400"}`}>
                {msgKeys}
              </span>
            )}
          </div>
          <p className="text-stone text-xs">As chaves são salvas no banco de dados. O painel exibe apenas uma prévia mascarada.</p>
        </div>

        <div>
          <FieldLabel>Provedor ativo</FieldLabel>
          <div className="flex gap-3">
            {(["claude", "openai"] as const).map((p) => (
              <button
                key={p}
                onClick={() => {
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

        <Sel label="Modelo" value={modelValue} onChange={(e) => upd("modelo_ia", e.target.value)}>
          {models.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </Sel>

        <div>
          <FieldLabel>
            Temperatura —{" "}
            <span className="text-gold">{settings.temperatura.toFixed(1)}</span>
            <span className="text-stone font-normal ml-2">(0 = determinístico · 1 = criativo)</span>
          </FieldLabel>
          <input
            type="range" min={0} max={1} step={0.1}
            value={settings.temperatura}
            onChange={(e) => upd("temperatura", parseFloat(e.target.value))}
            className="w-full accent-gold"
          />
          <div className="flex justify-between text-stone text-xs mt-0.5">
            <span>0.0</span><span>0.5</span><span>1.0</span>
          </div>
        </div>

        <div>
          <Inp
            label="Máx. tokens por resposta"
            type="number" min={100} max={4096} step={50}
            value={settings.max_tokens}
            onChange={(e) => upd("max_tokens", Number(e.target.value))}
          />
          <p className="text-stone text-xs mt-1">Recomendado: 512–1024 para chatbot de atendimento.</p>
        </div>

        <div className="bg-surface-03 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-parchment text-sm font-medium">Testar conexão com a IA</span>
            <button
              onClick={test}
              disabled={testing || !status.ativo}
              className="flex items-center gap-2 bg-surface-02 hover:bg-surface-03/80 disabled:opacity-50 border border-surface-03 text-parchment py-1.5 px-4 rounded-lg text-xs transition-colors"
            >
              {testing ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} className="text-gold" />}
              {testing ? "Testando..." : "Testar agora"}
            </button>
          </div>
          {testResult && (
            <div className="space-y-2">
              <div className="bg-surface-02 rounded-lg px-3 py-2 text-parchment text-sm">{testResult.resposta}</div>
              <div className="flex gap-4 text-stone text-xs">
                <span>Latência: <span className="text-parchment">{testResult.latencia_ms}ms</span></span>
                <span>Tokens: <span className="text-parchment">{testResult.tokens}</span></span>
              </div>
            </div>
          )}
          {!status.ativo && (
            <p className="text-stone text-xs">Configure pelo menos uma chave de API para habilitar o teste.</p>
          )}
        </div>

        <SaveBar saving={savingAI} msg={msgAI} onSave={saveAI} label="Salvar configuração de IA" />
      </Section>

      {/* ── 3. Prompt & Comportamento ─────────────────────────────────────────── */}
      <Section
        icon={<Brain size={18} />}
        title="Prompt & Comportamento"
        subtitle="Instruções, tom de voz, regras e limites do bot"
      >
        <Txt
          label="Prompt base"
          hint="Instruções principais. Explique quem o bot é e o que deve fazer."
          rows={5}
          value={settings.prompt_base}
          onChange={(e) => upd("prompt_base", e.target.value)}
          placeholder="Você é o assistente virtual da pizzaria Moschettieri..."
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Txt
            label="Tom de voz"
            rows={2}
            value={settings.tom_de_voz}
            onChange={(e) => upd("tom_de_voz", e.target.value)}
            placeholder="Simpático, acolhedor e objetivo. Use emojis com moderação."
          />
          <Txt
            label="Objetivo principal"
            rows={2}
            value={settings.objetivo}
            onChange={(e) => upd("objetivo", e.target.value)}
            placeholder="Ajudar o cliente a fazer pedidos e tirar dúvidas sobre o cardápio."
          />
        </div>

        <Txt
          label="Regras fixas"
          hint="O bot sempre seguirá estas regras, independente da conversa."
          rows={4}
          value={settings.regras_fixas}
          onChange={(e) => upd("regras_fixas", e.target.value)}
          placeholder={"- Nunca invente preços\n- Pergunte o tamanho antes de confirmar o pedido\n- Se não souber, transfira para humano"}
        />

        <Txt
          label="Limitações e proibições"
          rows={3}
          value={settings.limitacoes_proibicoes}
          onChange={(e) => upd("limitacoes_proibicoes", e.target.value)}
          placeholder={"- Não discuta concorrentes\n- Não faça promessas de prazo\n- Não forneça dados pessoais"}
        />

        <Txt
          label="Quando transferir ao atendente"
          rows={3}
          value={settings.instrucoes_transferencia}
          onChange={(e) => upd("instrucoes_transferencia", e.target.value)}
          placeholder="Se o cliente reclamar ou mencionar problema com pedido anterior, transfira imediatamente."
        />

        <SaveBar saving={savingPrompt} msg={msgPrompt} onSave={savePrompt} label="Salvar prompt" />

        <Simulator settings={settings} />
      </Section>
    </div>
  );
}
