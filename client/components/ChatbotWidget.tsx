import { useEffect, useRef, useState } from "react";
import { X, Send, Minimize2 } from "lucide-react";
import { chatbotPublicApi, type ChatbotSettings, type ChatbotMessage } from "@/lib/chatbotApi";

interface Msg { role: "visitor" | "bot" | "human"; content: string; ts: number }

function useSessionId() {
  const [id] = useState(() => {
    const stored = sessionStorage.getItem("chatbot_sid");
    if (stored) return stored;
    const next = `web-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    sessionStorage.setItem("chatbot_sid", next);
    return next;
  });
  return id;
}

export default function ChatbotWidget() {
  const [config, setConfig] = useState<ChatbotSettings | null>(null);
  const [open, setOpen]     = useState(false);
  const [started, setStarted] = useState(false);
  const [msgs, setMsgs]     = useState<Msg[]>([]);
  const [input, setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [awaiting, setAwaiting] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);
  const sessionId = useSessionId();

  // Load config
  useEffect(() => {
    chatbotPublicApi.config().then(setConfig).catch(() => {});
  }, []);

  // Auto-trigger
  useEffect(() => {
    if (!config?.ativo || !config.tempo_disparo_auto || open) return;
    const t = setTimeout(() => setOpen(true), config.tempo_disparo_auto * 1000);
    return () => clearTimeout(t);
  }, [config, open]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, loading]);

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);

  const startSession = async (cfg: ChatbotSettings) => {
    if (started) return;
    setStarted(true);
    try {
      const r = await chatbotPublicApi.session({
        session_id: sessionId,
        pagina_origem: window.location.pathname,
      });
      const welcomeText = r.config?.mensagem_inicial ?? cfg.mensagem_inicial;
      if (welcomeText) {
        setMsgs([{ role: "bot", content: welcomeText, ts: Date.now() }]);
      }
    } catch {
      setMsgs([{ role: "bot", content: cfg.mensagem_inicial || "Olá! Como posso ajudar?", ts: Date.now() }]);
    }
  };

  const handleOpen = () => {
    setOpen(true);
    if (config && !started) startSession(config);
  };

  const handleClose = () => {
    setOpen(false);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMsgs((m) => [...m, { role: "visitor", content: text, ts: Date.now() }]);
    setLoading(true);
    try {
      const r = await chatbotPublicApi.message({ session_id: sessionId, mensagem: text });
      if (r.awaiting_human) setAwaiting(true);
      setMsgs((m) => [
        ...m,
        { role: r.awaiting_human ? "human" : "bot", content: r.resposta || "...", ts: Date.now() },
      ]);
    } catch {
      setMsgs((m) => [...m, { role: "bot", content: "Desculpe, ocorreu um erro. Tente novamente.", ts: Date.now() }]);
    } finally {
      setLoading(false);
    }
  };

  if (!config?.ativo) return null;

  const isRight = config.posicao_widget !== "bottom-left";
  const posClass = isRight ? "right-5" : "left-5";

  return (
    <div className={`fixed bottom-5 ${posClass} z-[9999] flex flex-col items-end gap-3`}
      style={{ fontFamily: "inherit" }}>

      {/* Chat window */}
      {open && (
        <div className="w-[340px] sm:w-[380px] bg-[#1a1a1a] rounded-2xl shadow-2xl border border-white/10 overflow-hidden flex flex-col"
          style={{ maxHeight: "calc(100vh - 100px)" }}>

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 flex-shrink-0"
            style={{ background: config.cor_primaria }}>
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-sm">💬</div>
              <div>
                <p className="text-white text-sm font-bold leading-tight">{config.nome_bot}</p>
                {awaiting && <p className="text-white/70 text-[10px]">Aguardando atendente humano</p>}
              </div>
            </div>
            <button onClick={handleClose} className="text-white/70 hover:text-white transition-colors p-1">
              <Minimize2 size={16} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#121212]"
            style={{ minHeight: 200, maxHeight: 400 }}>
            {msgs.length === 0 && (
              <p className="text-[#666] text-xs text-center pt-4">Iniciando conversa...</p>
            )}
            {msgs.map((m, i) => {
              const isVisitor = m.role === "visitor";
              return (
                <div key={i} className={`flex ${isVisitor ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[82%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                      isVisitor
                        ? "text-white rounded-br-sm"
                        : "bg-[#2a2a2a] text-[#e8e8e8] rounded-bl-sm"
                    }`}
                    style={isVisitor ? { background: config.cor_primaria } : {}}
                  >
                    {m.content}
                  </div>
                </div>
              );
            })}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-[#2a2a2a] px-3 py-2 rounded-2xl rounded-bl-sm">
                  <span className="flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="w-1.5 h-1.5 bg-[#666] rounded-full animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="flex gap-2 px-3 py-3 bg-[#1a1a1a] border-t border-white/5 flex-shrink-0">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Digite sua mensagem..."
              disabled={loading}
              className="flex-1 bg-[#2a2a2a] border border-white/10 rounded-xl px-3 py-2 text-[#e8e8e8] placeholder-[#555] text-sm focus:outline-none focus:border-white/20 disabled:opacity-50"
            />
            <button onClick={send} disabled={loading || !input.trim()}
              className="w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-40 transition-opacity flex-shrink-0"
              style={{ background: config.cor_primaria }}>
              <Send size={15} className="text-white" />
            </button>
          </div>

          <p className="text-[#333] text-[9px] text-center pb-1.5 bg-[#1a1a1a]">
            Powered by IA · {config.nome_bot}
          </p>
        </div>
      )}

      {/* FAB button */}
      {!open && (
        <button
          onClick={handleOpen}
          className="w-14 h-14 rounded-full shadow-2xl flex items-center justify-center text-2xl transition-transform hover:scale-110 active:scale-95 relative"
          style={{ background: config.cor_primaria }}
          aria-label={`Abrir chat com ${config.nome_bot}`}
        >
          💬
        </button>
      )}

      {/* Close FAB when chat is open */}
      {open && (
        <button
          onClick={handleClose}
          className="w-12 h-12 rounded-full shadow-xl flex items-center justify-center transition-transform hover:scale-110 active:scale-95 bg-[#1a1a1a] border border-white/10"
          aria-label="Fechar chat"
        >
          <X size={18} className="text-[#999]" />
        </button>
      )}
    </div>
  );
}
