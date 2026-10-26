import { useCallback, useEffect, useMemo, useState } from "react";
import { MessageCircle, Phone, Send, X, RefreshCw, UserCheck } from "lucide-react";
import { chatbotAdminApi, type ChatbotConversation, type ChatbotMessage } from "@/lib/chatbotApi";
import { agenteWhatsAppApi, type ApiAgenteWhatsAppConversation, type ApiAgenteWhatsAppMessage } from "@/lib/api";

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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [chat, wa] = await Promise.all([
        chatbotAdminApi.listConversations("em_humano", 1),
        agenteWhatsAppApi.listConversations({ limit: 100 }),
      ]);
      setChatbot(chat.items ?? []);
      setWhatsapp(wa ?? []);
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
    setSelected(item);
    if (channel === "chatbot") {
      const detail = await chatbotAdminApi.getConversation(item.id);
      setMessages(detail.messages ?? []);
    } else {
      const detail = await agenteWhatsAppApi.getSession(item.id);
      setMessages(detail.messages ?? []);
    }
  };

  const send = async () => {
    const body = draft.trim();
    if (!body || !selected) return;
    setDraft("");
    if (channel === "chatbot") {
      await chatbotAdminApi.reply(selected.id, body);
      const detail = await chatbotAdminApi.getConversation(selected.id);
      setMessages(detail.messages ?? []);
    } else {
      const msg = await agenteWhatsAppApi.addMessage(selected.id, { direction: "outbound", sender_type: "human", body, message_type: "text" });
      setMessages((current) => [...current, msg]);
    }
    void load();
  };

  const items = channel === "chatbot" ? chatbot : whatsapp;

  return (
    <>
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => { setChannel("chatbot"); setOpen(true); }} className="relative inline-flex min-h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm font-bold text-parchment">
          <MessageCircle size={16} /> Chatbot {pending.chatbot > 0 && <span className="rounded-full bg-orange-500 px-1.5 text-[10px] text-white">{pending.chatbot}</span>}
        </button>
        <button type="button" onClick={() => { setChannel("whatsapp"); setOpen(true); }} className="relative inline-flex min-h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm font-bold text-parchment">
          <Phone size={16} /> WhatsApp {pending.whatsapp > 0 && <span className="rounded-full bg-emerald-600 px-1.5 text-[10px] text-white">{pending.whatsapp}</span>}
        </button>
      </div>
      {open && <aside className="fixed bottom-0 right-0 top-[68px] z-40 flex w-full max-w-md flex-col border-l border-surface-03 bg-surface-00 shadow-2xl">
        <header className="flex items-center justify-between border-b border-surface-03 p-4"><div><h2 className="font-black text-cream">Atendimento</h2><p className="text-xs text-stone">{loading ? "Atualizando..." : `${items.length} conversa(s)`}</p></div><div className="flex gap-2"><button type="button" onClick={() => void load()} aria-label="Atualizar"><RefreshCw size={16} /></button><button type="button" onClick={() => { setOpen(false); setSelected(null); }} aria-label="Fechar"><X size={18} /></button></div></header>
        <div className="flex border-b border-surface-03 p-2"><button type="button" onClick={() => { setChannel("chatbot"); setSelected(null); }} className={`flex-1 rounded-lg p-2 text-sm font-bold ${channel === "chatbot" ? "bg-gold/20 text-gold" : "text-stone"}`}>Chatbot ({pending.chatbot})</button><button type="button" onClick={() => { setChannel("whatsapp"); setSelected(null); }} className={`flex-1 rounded-lg p-2 text-sm font-bold ${channel === "whatsapp" ? "bg-gold/20 text-gold" : "text-stone"}`}>WhatsApp ({pending.whatsapp})</button></div>
        {!selected ? <div className="flex-1 space-y-2 overflow-y-auto p-3">{items.length === 0 && <p className="py-10 text-center text-sm text-stone">Nenhum atendimento pendente.</p>}{items.map((item) => <button type="button" key={item.id} onClick={() => void openConversation(item)} className="w-full rounded-xl border border-surface-03 bg-surface-02 p-3 text-left"><div className="flex items-center justify-between"><span className="font-bold text-cream">{"nome_cliente" in item ? (item.nome_cliente || "Visitante") : (item.phone || "WhatsApp")}</span><span className="text-xs text-stone">{"unread_count" in item ? item.unread_count : item.status}</span></div><p className="mt-1 truncate text-xs text-stone">{"last_message" in item ? (item.last_message?.body || "") : (item.resumo_conversa || "Solicitação de atendimento")}</p></button>)}</div> : <div className="flex min-h-0 flex-1 flex-col"><div className="flex items-center gap-2 border-b border-surface-03 p-3"><button type="button" onClick={() => setSelected(null)} className="text-sm text-gold">Voltar</button><span className="truncate font-bold text-cream">{"nome_cliente" in selected ? (selected.nome_cliente || "Visitante") : selected.phone}</span><UserCheck size={15} className="ml-auto text-emerald-400" /></div><div className="flex-1 space-y-2 overflow-y-auto p-3">{messages.map((message) => <div key={message.id} className={`rounded-xl p-2 text-sm ${("sender" in message ? message.sender === "visitor" : message.direction === "inbound") ? "bg-surface-02 text-parchment" : "ml-8 bg-gold/15 text-cream"}`}>{"mensagem" in message ? message.mensagem : message.body}</div>)}</div><div className="flex gap-2 border-t border-surface-03 p-3"><input value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void send(); }} className="min-w-0 flex-1 rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-sm text-cream" placeholder="Responder..." /><button type="button" onClick={() => void send()} className="rounded-lg bg-gold p-2 text-black"><Send size={16} /></button></div></div>}
      </aside>}
    </>
  );
}
