import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as SheetPrimitive from "@radix-ui/react-dialog";
import { MessageCircle, Phone, Send, X, RefreshCw, Volume2 } from "lucide-react";
import { Sheet, SheetClose, SheetDescription, SheetOverlay, SheetPortal, SheetTitle } from "@/components/ui/sheet";
import { chatbotAdminApi, type ChatbotConversation, type ChatbotMessage } from "@/lib/chatbotApi";
import { agenteWhatsAppApi, resolveAssetUrl, type ApiAgenteWhatsAppConversation, type ApiAgenteWhatsAppMessage } from "@/lib/api";
import WhatsAppAttendanceControls, { WhatsAppAttendanceBadge } from "./WhatsAppAttendanceControls";
import { whatsappAttendance } from "@/lib/whatsappAttendance";

type Channel = "chatbot" | "whatsapp";

export default function OperationsContactPanel() {
  const [channel, setChannel] = useState<Channel>("chatbot");
  const [open, setOpen] = useState(false);
  const [chatbot, setChatbot] = useState<ChatbotConversation[]>([]);
  const [whatsapp, setWhatsapp] = useState<ApiAgenteWhatsAppConversation[]>([]);
  const [selected, setSelected] = useState<ChatbotConversation | ApiAgenteWhatsAppConversation | null>(null);
  const [messages, setMessages] = useState<Array<ChatbotMessage | ApiAgenteWhatsAppMessage>>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const actionRef = useRef(false);
  const detailRequest = useRef(0);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const selectedWhatsApp = selected && "ai_enabled" in selected ? selected : null;
  const canReply = selected && detailId === selected.id && !detailLoading && !busy && (
    channel === "chatbot" || whatsappAttendance(selectedWhatsApp).canSendHuman
  );

  const resetConversation = () => {
    detailRequest.current += 1;
    setSelected(null);
    setMessages([]);
    setDetailId(null);
    setDetailLoading(false);
    setDraft("");
    setError("");
  };

  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) resetConversation();
  };

  const openChannel = (nextChannel: Channel, trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    setChannel(nextChannel);
    resetConversation();
    setOpen(true);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [chat, wa] = await Promise.all([
        chatbotAdminApi.listConversations("em_humano", 1),
        agenteWhatsAppApi.listConversations({ limit: 100 }),
      ]);
      setChatbot(chat.items ?? []);
      setWhatsapp(wa ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar atendimentos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); const id = window.setInterval(() => void load(), 15000); return () => window.clearInterval(id); }, [load]);

  const pending = useMemo(() => ({
    chatbot: chatbot.filter((item) => item.status === "em_humano").length,
    whatsapp: whatsapp.filter((item) => item.status === "open" || item.unread_count > 0).length,
  }), [chatbot, whatsapp]);

  const openConversation = async (item: ChatbotConversation | ApiAgenteWhatsAppConversation) => {
    const request = ++detailRequest.current;
    setSelected(item);
    setDraft("");
    setMessages([]);
    setDetailId(null);
    setDetailLoading(true);
    setError("");
    try {
      if (channel === "chatbot") {
        const detail = await chatbotAdminApi.getConversation(item.id);
        if (request !== detailRequest.current) return;
        setSelected(detail);
        setMessages(detail.messages ?? []);
      } else {
        const detail = await agenteWhatsAppApi.getSession(item.id);
        if (request !== detailRequest.current) return;
        setSelected({ ...item, ...detail.session } as ApiAgenteWhatsAppConversation);
        setMessages(detail.messages ?? []);
      }
      setDetailId(item.id);
    } catch (err) {
      if (request === detailRequest.current) setError(err instanceof Error ? err.message : "Falha ao carregar conversa.");
    } finally {
      if (request === detailRequest.current) setDetailLoading(false);
    }
  };

  // Keep the ownership indicator and delivery state current across both screens.
  useEffect(() => {
    if (!open || channel !== "whatsapp" || !selected) return;
    const sessionId = selected.id;
    const refresh = async () => {
      if (actionRef.current) return;
      const request = detailRequest.current;
      try {
        const detail = await agenteWhatsAppApi.getSession(sessionId);
        if (request !== detailRequest.current || actionRef.current) return;
        setSelected((current) => current?.id === sessionId ? { ...current, ...detail.session } as ApiAgenteWhatsAppConversation : current);
        setMessages(detail.messages ?? []);
        setDetailId(sessionId);
      } catch (err) {
        if (request !== detailRequest.current || actionRef.current) return;
        setDetailId(null);
        setError(err instanceof Error ? err.message : "Falha ao confirmar controle da conversa.");
      }
    };
    const interval = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(interval);
  }, [open, channel, selected?.id]);

  const changeAttendance = async (human: boolean) => {
    if (!selectedWhatsApp || actionRef.current) return;
    const item = selectedWhatsApp;
    const request = ++detailRequest.current;
    actionRef.current = true;
    setBusy(true);
    setError("");
    try {
      const updated = await (human ? agenteWhatsAppApi.assumeSession(item.id) : agenteWhatsAppApi.returnSessionToAI(item.id));
      setWhatsapp((current) => current.map((row) => row.id === updated.id ? { ...row, ...updated } : row));
      if (request === detailRequest.current) {
        setSelected({ ...item, ...updated });
        setDetailId(updated.id);
      }
    } catch (err) {
      if (request === detailRequest.current) {
        setDetailId(null);
        setError(err instanceof Error ? err.message : "Falha ao alterar controle da conversa.");
      }
    } finally {
      actionRef.current = false;
      setBusy(false);
    }
  };

  const send = async () => {
    const body = draft.trim();
    if (!body || !selected || !canReply || actionRef.current) return;
    const request = ++detailRequest.current;
    actionRef.current = true;
    setBusy(true);
    setError("");
    try {
      if (channel === "chatbot") {
        await chatbotAdminApi.reply(selected.id, body);
        const detail = await chatbotAdminApi.getConversation(selected.id);
        if (request === detailRequest.current) setMessages(detail.messages ?? []);
      } else {
        const msg = await agenteWhatsAppApi.sendHumanMessage(selected.id, { body, raw_payload: { source: "operations_contact_panel" } });
        if (request === detailRequest.current) setMessages((current) => [...current, msg]);
      }
      if (request === detailRequest.current) setDraft("");
      void load();
    } catch (err) {
      if (request === detailRequest.current) {
        setDetailId(null);
        setError(err instanceof Error ? err.message : "Falha ao enviar mensagem. O texto foi preservado.");
      }
    } finally {
      actionRef.current = false;
      setBusy(false);
    }
  };

  const items = channel === "chatbot" ? chatbot : whatsapp;

  return (
    <>
      <div className="flex items-center gap-2">
        <button type="button" aria-haspopup="dialog" aria-expanded={open && channel === "chatbot"} onClick={(event) => openChannel("chatbot", event.currentTarget)} className="relative inline-flex min-h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm font-bold text-parchment">
          <MessageCircle size={16} /> Chatbot {pending.chatbot > 0 && <span className="rounded-full bg-orange-500 px-1.5 text-[10px] text-white">{pending.chatbot}</span>}
        </button>
        <button type="button" aria-haspopup="dialog" aria-expanded={open && channel === "whatsapp"} onClick={(event) => openChannel("whatsapp", event.currentTarget)} className="relative inline-flex min-h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm font-bold text-parchment">
          <Phone size={16} /> WhatsApp {pending.whatsapp > 0 && <span className="rounded-full bg-emerald-600 px-1.5 text-[10px] text-white">{pending.whatsapp}</span>}
        </button>
      </div>
      <Sheet open={open} onOpenChange={changeOpen}>
        <SheetPortal>
          <SheetOverlay />
          <SheetPrimitive.Content
            onCloseAutoFocus={(event) => { event.preventDefault(); triggerRef.current?.focus(); }}
            className="fixed inset-y-0 right-0 z-50 flex h-dvh w-full max-w-md flex-col overflow-hidden border-l border-surface-03 bg-surface-00 text-parchment shadow-2xl outline-none"
          >
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-surface-03 p-4 pt-[max(1rem,env(safe-area-inset-top))]">
          <div className="min-w-0"><SheetTitle className="font-black text-cream">Atendimento</SheetTitle><SheetDescription className="text-xs text-stone">{loading ? "Atualizando..." : `${items.length} conversa(s)`}</SheetDescription></div>
          <div className="flex shrink-0 gap-1">
            <button type="button" onClick={() => void load()} aria-label="Atualizar atendimentos" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-stone hover:bg-surface-02 hover:text-cream focus-visible:outline focus-visible:outline-2 focus-visible:outline-gold"><RefreshCw size={18} /></button>
            <SheetClose asChild><button type="button" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 text-sm font-bold text-cream hover:bg-surface-02 focus-visible:outline focus-visible:outline-2 focus-visible:outline-gold"><X size={18} aria-hidden="true" />Fechar</button></SheetClose>
          </div>
        </div>
        <div className="flex border-b border-surface-03 p-2">
          <button type="button" onClick={() => { setChannel("chatbot"); resetConversation(); }} className={`flex-1 rounded-lg p-2 text-sm font-bold ${channel === "chatbot" ? "bg-gold/20 text-gold" : "text-stone"}`}>Chatbot ({pending.chatbot})</button>
          <button type="button" onClick={() => { setChannel("whatsapp"); resetConversation(); }} className={`flex-1 rounded-lg p-2 text-sm font-bold ${channel === "whatsapp" ? "bg-gold/20 text-gold" : "text-stone"}`}>WhatsApp ({pending.whatsapp})</button>
        </div>
        {error && <p role="alert" className="m-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200">{error}</p>}
        {!selected ? (
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {items.length === 0 && <p className="py-10 text-center text-sm text-stone">Nenhum atendimento pendente.</p>}
            {items.map((item) => <button type="button" key={item.id} onClick={() => void openConversation(item)} className="w-full rounded-xl border border-surface-03 bg-surface-02 p-3 text-left">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-bold text-cream">{"nome_cliente" in item ? (item.nome_cliente || "Visitante") : (item.customer_name || item.phone || "WhatsApp")}</span>
                <span className="text-xs text-stone">{"unread_count" in item ? item.unread_count : item.status}</span>
              </div>
              {"ai_enabled" in item && <div className="mt-2"><WhatsAppAttendanceBadge session={item} /></div>}
              <p className="mt-1 truncate text-xs text-stone">{"last_message" in item ? (item.last_message?.body || "") : (item.resumo_conversa || "Solicitação de atendimento")}</p>
            </button>)}
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="space-y-3 border-b border-surface-03 p-3">
              <div className="flex items-center gap-2">
                <button type="button" onClick={resetConversation} className="text-sm text-gold">Voltar</button>
                <span className="truncate font-bold text-cream">{"nome_cliente" in selected ? (selected.nome_cliente || "Visitante") : (selected.customer_name || selected.phone)}</span>
              </div>
              {selectedWhatsApp && <WhatsAppAttendanceControls session={selectedWhatsApp} busy={busy || detailLoading || detailId !== selected.id} onAssume={() => void changeAttendance(true)} onReturnToAI={() => void changeAttendance(false)} />}
            </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
              {detailLoading && <p role="status" className="text-xs text-stone">Carregando conversa...</p>}
              {messages.map((message) => <div key={message.id} className={`rounded-xl p-2 text-sm ${("sender" in message ? message.sender === "visitor" : message.direction === "inbound") ? "bg-surface-02 text-parchment" : "ml-8 bg-gold/15 text-cream"}`}>
                {"message_type" in message && message.message_type === "audio" && (message.media_url || message.media_storage_key) && <div className="mb-1 flex items-center gap-1 text-[11px] text-gold"><Volume2 size={12} /> Áudio</div>}
                {"message_type" in message && message.message_type === "audio" && (message.media_url || message.media_storage_key) && <audio controls preload="metadata" src={resolveAssetUrl(message.media_url || message.media_storage_key)} className="my-2 h-9 w-full min-w-[220px] max-w-full" />}
                {"mensagem" in message ? message.mensagem : (message.body || (message.message_type === "audio" ? "Áudio" : "Mídia"))}
                {"provider_status" in message && message.direction === "outbound" && <p className="mt-1 text-[10px] text-stone">{message.error || message.provider_status || "Status de entrega não confirmado"}</p>}
              </div>)}
            </div>
            <div className="flex gap-2 border-t border-surface-03 p-3">
              <input value={draft} disabled={!canReply} aria-label="Mensagem de atendimento" onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.nativeEvent.isComposing) void send(); }} className="min-w-0 flex-1 rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-sm text-cream disabled:opacity-50" placeholder={canReply ? "Responder..." : "Assuma a conversa para responder"} />
              <button type="button" onClick={() => void send()} disabled={!canReply || !draft.trim()} aria-label="Enviar mensagem humana" className="rounded-lg bg-gold p-2 text-black disabled:opacity-50"><Send size={16} /></button>
            </div>
          </div>
        )}
          </SheetPrimitive.Content>
        </SheetPortal>
      </Sheet>
    </>
  );
}
