import { useEffect, useRef, useState, useCallback } from "react";
import { X, Send, Minimize2, UserCheck } from "lucide-react";
import {
  chatbotPublicApi,
  type ChatbotSettings,
  type PublicAutomation,
} from "@/lib/chatbotApi";
import { useApp } from "@/context/AppContext";

interface Msg {
  id?:    string;
  role:   "visitor" | "bot" | "human" | "system";
  content: string;
  ts:     number;
}

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

// ─────────────────────────────────────────────────────────────────────────────

export default function ChatbotWidget() {
  const { customer }                = useApp();
  const [config, setConfig]         = useState<ChatbotSettings | null>(null);
  const [automations, setAutomations] = useState<PublicAutomation[]>([]);
  const [open, setOpen]             = useState(false);
  const [started, setStarted]       = useState(false);
  const [msgs, setMsgs]             = useState<Msg[]>([]);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [awaiting, setAwaiting]     = useState(false);
  const [convStatus, setConvStatus] = useState<string>("aberta");

  const bottomRef       = useRef<HTMLDivElement>(null);
  const inputRef        = useRef<HTMLInputElement>(null);
  const pollRef         = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusPollRef   = useRef<ReturnType<typeof setInterval> | null>(null);
  const shownIds        = useRef(new Set<string>());
  const autoFiredRef    = useRef(false);
  const userDismissed   = useRef(false);  // true after user manually closes — blocks all auto-triggers
  const sessionId       = useSessionId();

  // ── Load config + automations ──────────────────────────────────────────────
  useEffect(() => {
    chatbotPublicApi.config().then(setConfig).catch(() => {});
    chatbotPublicApi.automations().then(setAutomations).catch(() => {});
  }, []);

  // ── Config-based auto-trigger (fires once, never after user dismisses) ────
  useEffect(() => {
    if (!config?.ativo || !config.tempo_disparo_auto) return;
    if (autoFiredRef.current) return;
    const t = setTimeout(() => {
      if (userDismissed.current || autoFiredRef.current) return;
      autoFiredRef.current = true;
      setOpen(true);
    }, config.tempo_disparo_auto * 1000);
    return () => clearTimeout(t);
  }, [config]); // 'open' removed from deps — prevents re-trigger on close

  // ── Automation rules evaluation ───────────────────────────────────────────
  useEffect(() => {
    if (!config?.ativo || !automations.length || autoFiredRef.current) return;

    const pathname = window.location.pathname;
    const timers: ReturnType<typeof setTimeout>[] = [];

    for (const auto of automations) {
      if (auto.gatilho === "pagina_especifica") {
        if (pathname.includes(auto.condicao)) {
          const t = setTimeout(() => {
            if (autoFiredRef.current || userDismissed.current) return;
            autoFiredRef.current = true;
            setOpen(true);
            setMsgs((m) => m.length === 0 ? [{ role: "bot", content: auto.mensagem, ts: Date.now() }] : m);
          }, 800);
          timers.push(t);
          break;
        }
      } else if (auto.gatilho === "produto_visualizado" && pathname.startsWith("/product/")) {
        const t = setTimeout(() => {
          if (autoFiredRef.current || userDismissed.current) return;
          autoFiredRef.current = true;
          setOpen(true);
          setMsgs((m) => m.length === 0 ? [{ role: "bot", content: auto.mensagem, ts: Date.now() }] : m);
        }, 2500);
        timers.push(t);
        break;
      } else if (auto.gatilho === "tempo_na_pagina") {
        const delay = (parseInt(auto.condicao, 10) || 30) * 1000;
        const t = setTimeout(() => {
          if (autoFiredRef.current || userDismissed.current) return;
          autoFiredRef.current = true;
          setOpen(true);
          setMsgs((m) => m.length === 0 ? [{ role: "bot", content: auto.mensagem, ts: Date.now() }] : m);
        }, delay);
        timers.push(t);
        break;
      }
    }

    return () => timers.forEach(clearTimeout);
  }, [config, automations]);

  // ── Light status poll — detects admin takeover while widget is open ────────
  useEffect(() => {
    if (!open || !started || awaiting) {
      if (statusPollRef.current) { clearInterval(statusPollRef.current); statusPollRef.current = null; }
      return;
    }
    statusPollRef.current = setInterval(async () => {
      try {
        const r = await chatbotPublicApi.history(sessionId);
        if (r.status === "em_humano") {
          setAwaiting(true);
          setConvStatus("em_humano");
        }
      } catch {}
    }, 6000);
    return () => { if (statusPollRef.current) { clearInterval(statusPollRef.current); statusPollRef.current = null; } };
  }, [open, started, awaiting, sessionId]);

  // ── Scroll to bottom ───────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, loading]);

  // ── Focus input on open ────────────────────────────────────────────────────
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);

  // ── Human-reply polling ────────────────────────────────────────────────────
  useEffect(() => {
    if (!awaiting) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }

    const applyHistory = (r: { status: string; messages: Array<{ id: string; sender: string; tipo: string; mensagem: string; timestamp: string }> }, showNew: boolean) => {
      setConvStatus(r.status);
      for (const m of r.messages) {
        const isNew = !shownIds.current.has(m.id);
        shownIds.current.add(m.id);
        if (!isNew || !showNew) continue;
        if (m.sender === "visitor") continue;
        const role = m.sender === "human"
          ? (m.tipo === "system" ? "system" : "human")
          : "bot";
        setMsgs((prev) => [...prev, { id: m.id, role, content: m.mensagem, ts: new Date(m.timestamp).getTime() }]);
      }
      if (r.status === "aberta" || r.status === "encerrada") setAwaiting(false);
    };

    let cancelled = false;
    // Hydrate shownIds with all existing messages so polling only shows NEW ones
    chatbotPublicApi.history(sessionId)
      .then((r) => { if (!cancelled) applyHistory(r, false); })
      .catch(() => {})
      .finally(() => {
        if (cancelled) return;
        pollRef.current = setInterval(async () => {
          try {
            const r = await chatbotPublicApi.history(sessionId);
            applyHistory(r, true);
          } catch {}
        }, 3000);
      });

    return () => {
      cancelled = true;
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [awaiting, sessionId]);

  // ── Start session ──────────────────────────────────────────────────────────
  const startSession = useCallback(async (cfg: ChatbotSettings) => {
    if (started) return;
    setStarted(true);
    try {
      const r = await chatbotPublicApi.session({
        session_id:   sessionId,
        pagina_origem: window.location.pathname,
        user_agent:   navigator.userAgent,
        referrer:     document.referrer || undefined,
        customer_id:  customer?.id ?? undefined,
      });
      const welcome = r.config?.mensagem_inicial ?? cfg.mensagem_inicial;
      if (welcome) {
        setMsgs((m) => m.length === 0 ? [{ role: "bot", content: welcome, ts: Date.now() }] : m);
      }
    } catch {
      setMsgs((m) => m.length === 0 ? [{ role: "bot", content: cfg.mensagem_inicial || "Olá! Como posso ajudar?", ts: Date.now() }] : m);
    }
  }, [started, sessionId]);

  const handleOpen = useCallback(() => {
    setOpen(true);
    if (config && !started) startSession(config);
  }, [config, started, startSession]);

  const handleClose = () => {
    setOpen(false);
    userDismissed.current = true;  // block all future auto-triggers for this session
  };

  // ── Send message ───────────────────────────────────────────────────────────
  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const localMsg: Msg = { role: "visitor", content: text, ts: Date.now() };
    setMsgs((m) => [...m, localMsg]);
    setLoading(true);
    try {
      const r = await chatbotPublicApi.message({
        session_id:  sessionId,
        mensagem:    text,
        page_url:    window.location.pathname,
        customer_id: customer?.id ?? undefined,
      });

      if (r.awaiting_human) {
        setAwaiting(true);
        setConvStatus("em_humano");
      }

      if (r.resposta) {
        const botMsg: Msg = { role: r.awaiting_human ? "system" : "bot", content: r.resposta, ts: Date.now() };
        setMsgs((m) => [...m, botMsg]);
      }
    } catch {
      setMsgs((m) => [...m, { role: "bot", content: "Desculpe, ocorreu um erro. Tente novamente.", ts: Date.now() }]);
    } finally {
      setLoading(false);
    }
  };

  // ── Render guard ───────────────────────────────────────────────────────────
  if (!config?.ativo) return null;

  const isRight   = config.posicao_widget !== "bottom-left";
  const posClass  = isRight ? "right-5" : "left-5";
  const alignClass = isRight ? "items-end" : "items-start";

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className={`fixed bottom-[80px] ${posClass} z-[9999] flex flex-col ${alignClass} gap-3`}
      style={{ fontFamily: "inherit" }}>

      {/* ── Chat window ── */}
      {open && (
        <div className="w-[290px] sm:w-[360px] bg-[#1a1a1a] rounded-2xl shadow-2xl border border-white/10 overflow-hidden flex flex-col"
          style={{ maxHeight: "calc(100vh - 160px)" }}>

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 flex-shrink-0"
            style={{ background: config.cor_primaria }}>
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-sm flex-shrink-0">💬</div>
              <div>
                <p className="text-white text-sm font-bold leading-tight">{config.nome_bot}</p>
                {awaiting
                  ? <p className="text-white/70 text-[10px] flex items-center gap-1"><UserCheck size={10} /> Aguardando atendente</p>
                  : <p className="text-white/70 text-[10px]">Online</p>
                }
              </div>
            </div>
            <button onClick={handleClose} className="text-white/70 hover:text-white transition-colors p-1">
              <Minimize2 size={16} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#121212]"
            style={{ minHeight: 140, maxHeight: 280 }}>
            {msgs.length === 0 && (
              <p className="text-[#555] text-xs text-center pt-6">Iniciando conversa...</p>
            )}
            {msgs.map((m, i) => {
              if (m.role === "system") return (
                <div key={i} className="flex justify-center">
                  <span className="text-[#555] text-[10px] bg-[#1e1e1e] border border-white/5 px-3 py-1 rounded-full">{m.content}</span>
                </div>
              );
              const isVisitor = m.role === "visitor";
              const isHuman   = m.role === "human";
              return (
                <div key={i} className={`flex ${isVisitor ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[82%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                      isVisitor  ? "text-white rounded-br-sm"
                      : isHuman  ? "bg-blue-900/60 text-blue-100 rounded-bl-sm"
                      :            "bg-[#2a2a2a] text-[#e8e8e8] rounded-bl-sm"
                    }`}
                    style={isVisitor ? { background: config.cor_primaria } : {}}
                  >
                    {isHuman && <p className="text-blue-400 text-[10px] mb-0.5 font-medium">Atendente</p>}
                    {m.content}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-[#2a2a2a] px-3 py-2 rounded-2xl rounded-bl-sm">
                  <span className="flex gap-1 items-center">
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="w-1.5 h-1.5 bg-[#555] rounded-full animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </span>
                </div>
              </div>
            )}

            {awaiting && !loading && (
              <p className="text-[#444] text-[10px] text-center py-1">Aguardando resposta do atendente...</p>
            )}

            {convStatus === "encerrada" && (
              <p className="text-[#444] text-[10px] text-center py-1">Conversa encerrada.</p>
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
              placeholder={convStatus === "encerrada" ? "Conversa encerrada." : "Digite sua mensagem..."}
              disabled={loading || convStatus === "encerrada"}
              className="flex-1 bg-[#2a2a2a] border border-white/10 rounded-xl px-3 py-2 text-[#e8e8e8] placeholder-[#444] text-sm focus:outline-none focus:border-white/20 disabled:opacity-40"
            />
            <button onClick={send} disabled={loading || !input.trim() || convStatus === "encerrada"}
              className="w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-30 transition-opacity flex-shrink-0"
              style={{ background: config.cor_primaria }}>
              <Send size={15} className="text-white" />
            </button>
          </div>

          <p className="text-[#2a2a2a] text-[9px] text-center pb-1.5 bg-[#1a1a1a] select-none">
            Powered by IA · {config.nome_bot}
          </p>
        </div>
      )}

      {/* ── FAB button ── */}
      {!open ? (
        <button
          onClick={handleOpen}
          className="w-14 h-14 rounded-full shadow-2xl flex items-center justify-center text-2xl transition-transform hover:scale-110 active:scale-95"
          style={{ background: config.cor_primaria }}
          aria-label={`Abrir chat com ${config.nome_bot}`}
        >
          💬
        </button>
      ) : (
        <button
          onClick={handleClose}
          className="w-12 h-12 rounded-full shadow-xl flex items-center justify-center transition-transform hover:scale-110 active:scale-95 bg-[#1a1a1a] border border-white/10"
          aria-label="Fechar chat"
        >
          <X size={18} className="text-[#888]" />
        </button>
      )}
    </div>
  );
}
