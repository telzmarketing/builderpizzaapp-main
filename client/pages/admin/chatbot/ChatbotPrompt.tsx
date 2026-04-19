import { useEffect, useState, useRef } from "react";
import { Save, Play, X } from "lucide-react";
import { chatbotAdminApi, chatbotPublicApi, type ChatbotSettings } from "@/lib/chatbotApi";

const Txt = ({ label, hint, ...p }: { label: string; hint?: string } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <div>
    <label className="block text-parchment text-xs font-medium mb-1">{label}</label>
    {hint && <p className="text-stone text-xs mb-1">{hint}</p>}
    <textarea {...p} className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold resize-none" />
  </div>
);

interface SimMsg { role: "user" | "bot"; content: string }

function Simulator({ settings }: { settings: ChatbotSettings }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<SimMsg[]>([]);
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
    } finally { setLoading(false); }
  };

  if (!open) return (
    <button onClick={() => setOpen(true)}
      className="flex items-center gap-2 bg-surface-02 hover:bg-surface-03 border border-surface-03 text-parchment font-medium py-2 px-4 rounded-lg text-sm transition-colors">
      <Play size={14} className="text-gold" /> Testar prompt (simulador)
    </button>
  );

  return (
    <div className="bg-surface-02 border border-gold/40 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-03">
        <span className="text-cream text-sm font-bold">Simulador — {settings.nome_bot}</span>
        <button onClick={() => { setOpen(false); setMsgs([]); }} className="text-stone hover:text-cream">
          <X size={16} />
        </button>
      </div>
      <div className="h-64 overflow-y-auto p-4 space-y-3">
        {msgs.length === 0 && <p className="text-stone text-xs text-center pt-8">Envie uma mensagem para testar o prompt atual.</p>}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] px-3 py-2 rounded-xl text-sm ${m.role === "user" ? "bg-gold/20 text-cream" : "bg-surface-03 text-parchment"}`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && <div className="flex justify-start"><div className="bg-surface-03 px-3 py-2 rounded-xl text-stone text-xs">Digitando...</div></div>}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 px-4 pb-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Mensagem de teste..."
          className="flex-1 bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold"
        />
        <button onClick={send} disabled={loading || !input.trim()}
          className="bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold px-4 py-2 rounded-lg text-sm transition-colors">
          →
        </button>
      </div>
      <p className="text-stone text-[10px] px-4 pb-3">O simulador usa o prompt salvo (não o rascunho). Salve antes de testar.</p>
    </div>
  );
}

export default function ChatbotPrompt() {
  const [settings, setSettings] = useState<ChatbotSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => { chatbotAdminApi.getSettings().then(setSettings); }, []);

  if (!settings) return <div className="text-stone text-center py-16">Carregando...</div>;

  const upd = (k: keyof ChatbotSettings, v: string) =>
    setSettings((prev) => prev ? { ...prev, [k]: v } : prev);

  const save = async () => {
    setSaving(true); setMsg("");
    try {
      const s = await chatbotAdminApi.updateSettings({
        prompt_base:              settings.prompt_base,
        regras_fixas:             settings.regras_fixas,
        tom_de_voz:               settings.tom_de_voz,
        objetivo:                 settings.objetivo,
        instrucoes_transferencia: settings.instrucoes_transferencia,
        limitacoes_proibicoes:    settings.limitacoes_proibicoes,
      });
      setSettings(s); setMsg("Prompt salvo!");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Erro.");
    } finally { setSaving(false); }
  };

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-cream font-bold text-base">Prompt e comportamento</h3>
        <div className="flex items-center gap-3">
          {msg && <span className={msg.includes("Erro") ? "text-red-400 text-xs" : "text-green-400 text-xs"}>{msg}</span>}
          <button onClick={save} disabled={saving}
            className="flex items-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold py-2 px-4 rounded-lg text-sm transition-colors">
            <Save size={14} /> {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>

      <Txt label="Prompt base" hint="Instruções principais para o bot. Explique quem ele é e o que deve fazer."
        rows={5} value={settings.prompt_base} onChange={(e) => upd("prompt_base", e.target.value)}
        placeholder="Você é o assistente virtual da pizzaria Moschettieri..." />

      <Txt label="Tom de voz" hint="Ex: simpático, formal, descontraído, objetivo"
        rows={2} value={settings.tom_de_voz} onChange={(e) => upd("tom_de_voz", e.target.value)}
        placeholder="Simpático, acolhedor e objetivo. Use emojis com moderação." />

      <Txt label="Objetivo principal"
        rows={2} value={settings.objetivo} onChange={(e) => upd("objetivo", e.target.value)}
        placeholder="Ajudar o cliente a fazer um pedido, tirar dúvidas sobre o cardápio e informar sobre promoções." />

      <Txt label="Regras fixas" hint="O bot SEMPRE seguirá estas regras, independente da conversa."
        rows={4} value={settings.regras_fixas} onChange={(e) => upd("regras_fixas", e.target.value)}
        placeholder="- Nunca invente preços&#10;- Sempre pergunte o tamanho da pizza antes de fechar o pedido&#10;- Se não souber responder, transfira para humano" />

      <Txt label="Limitações e proibições"
        rows={3} value={settings.limitacoes_proibicoes} onChange={(e) => upd("limitacoes_proibicoes", e.target.value)}
        placeholder="- Não discuta concorrentes&#10;- Não faça promessas de prazo&#10;- Não forneça dados pessoais de clientes" />

      <Txt label="Instruções para transferência ao humano"
        rows={3} value={settings.instrucoes_transferencia} onChange={(e) => upd("instrucoes_transferencia", e.target.value)}
        placeholder="Se o cliente pedir falar com atendente, reclamar ou mencionar problema com pedido anterior, transfira imediatamente." />

      <Simulator settings={settings} />
    </div>
  );
}
