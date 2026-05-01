import { useEffect, useState } from "react";
import { ArrowLeft, UserCheck, Send, X, Bot, RefreshCw } from "lucide-react";
import { chatbotAdminApi, type ChatbotConversation, type ChatbotMessage } from "@/lib/chatbotApi";

const STATUS_LABEL: Record<string, string> = { aberta: "Aberta", em_humano: "Humano", encerrada: "Encerrada" };
const STATUS_COLOR: Record<string, string> = {
  aberta:    "bg-blue-500/20 text-blue-400 border-blue-500/30",
  em_humano: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  encerrada: "bg-surface-03 text-stone border-surface-03",
};
const SENDER_LABEL: Record<string, string> = { visitor: "Cliente", bot: "Bot", human: "Atendente" };

function MessageBubble({ msg }: { msg: ChatbotMessage }) {
  const isVisitor = msg.sender === "visitor";
  const isSystem  = msg.tipo === "system";
  if (isSystem) return (
    <div className="flex justify-center">
      <span className="text-stone text-xs bg-surface-03 px-3 py-1 rounded-full">{msg.mensagem}</span>
    </div>
  );
  return (
    <div className={`flex gap-2 ${isVisitor ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] space-y-0.5`}>
        <p className={`text-[10px] ${isVisitor ? "text-right text-stone" : "text-stone"}`}>{SENDER_LABEL[msg.sender]}</p>
        <div className={`px-3 py-2 rounded-xl text-sm ${
          isVisitor ? "bg-gold/20 text-cream" : msg.sender === "human" ? "bg-blue-500/20 text-blue-100" : "bg-surface-03 text-parchment"
        }`}>{msg.mensagem}</div>
        {msg.latencia_ms && <p className="text-[10px] text-stone">{msg.latencia_ms}ms · {msg.tokens_consumidos ?? 0}tk</p>}
      </div>
    </div>
  );
}

function ConversationDetail({ conv, onBack, onRefresh }: {
  conv: ChatbotConversation; onBack: () => void; onRefresh: () => void;
}) {
  const [detail, setDetail] = useState<ChatbotConversation | null>(null);
  const [reply, setReply]   = useState("");
  const [sending, setSending] = useState(false);
  const [replyErr, setReplyErr] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => chatbotAdminApi.getConversation(conv.id)
    .then(setDetail).finally(() => setLoading(false));

  useEffect(() => { load(); }, [conv.id]);

  const takeover = async () => {
    await chatbotAdminApi.takeover(conv.id, "Assumido pelo painel admin");
    load(); onRefresh();
  };

  const returnToBot = async () => {
    await chatbotAdminApi.returnToBot(conv.id);
    load(); onRefresh();
  };

  const close = async () => {
    await chatbotAdminApi.closeConv(conv.id);
    load(); onRefresh();
  };

  const sendReply = async () => {
    const text = reply.trim();
    if (!text || sending) return;
    setSending(true); setReply(""); setReplyErr("");
    try {
      await chatbotAdminApi.reply(conv.id, text);
      load();
    } catch (e: unknown) {
      setReplyErr(e instanceof Error ? e.message : "Erro ao enviar resposta.");
    } finally { setSending(false); }
  };

  if (loading || !detail) return <div className="text-stone text-center py-16">Carregando...</div>;

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-stone hover:text-parchment transition-colors">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLOR[detail.status]}`}>
              {STATUS_LABEL[detail.status]}
            </span>
            {detail.nome_cliente && (
              <span className="text-cream text-xs font-semibold bg-gold/20 border border-gold/30 px-2 py-0.5 rounded-full">
                {detail.nome_cliente}
              </span>
            )}
            <span className="text-stone text-xs">{detail.pagina_origem || "/"}</span>
            {detail.intencao_detectada && (
              <span className="text-parchment text-xs bg-surface-03 px-2 py-0.5 rounded-full">{detail.intencao_detectada}</span>
            )}
          </div>
          <p className="text-stone text-xs mt-0.5">{new Date(detail.iniciada_em).toLocaleString("pt-BR")}</p>
        </div>
        <div className="flex gap-2">
          {detail.status === "aberta" && (
            <button onClick={takeover}
              className="flex items-center gap-1.5 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/30 text-orange-300 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors">
              <UserCheck size={13} /> Assumir
            </button>
          )}
          {detail.status === "em_humano" && (
            <button onClick={returnToBot}
              className="flex items-center gap-1.5 bg-surface-03 hover:bg-surface-02 border border-surface-03 text-parchment text-xs font-medium px-3 py-1.5 rounded-lg transition-colors">
              <Bot size={13} /> Devolver ao bot
            </button>
          )}
          {detail.status !== "encerrada" && (
            <button onClick={close}
              className="flex items-center gap-1.5 bg-surface-03 hover:bg-surface-02 border border-surface-03 text-stone text-xs font-medium px-3 py-1.5 rounded-lg transition-colors">
              <X size={13} /> Encerrar
            </button>
          )}
        </div>
      </div>

      {detail.resumo_conversa && (
        <div className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3">
          <p className="text-stone text-xs font-medium mb-1">Resumo</p>
          <p className="text-parchment text-sm">{detail.resumo_conversa}</p>
        </div>
      )}

      <div className="bg-surface-02 border border-surface-03 rounded-xl overflow-hidden">
        <div className="h-96 overflow-y-auto p-4 space-y-3">
          {(detail.messages ?? []).length === 0 && (
            <p className="text-stone text-xs text-center pt-8">Sem mensagens.</p>
          )}
          {(detail.messages ?? []).map((m) => <MessageBubble key={m.id} msg={m} />)}
        </div>

        {detail.status === "em_humano" && (
          <div className="px-4 pb-4 border-t border-surface-03 pt-3 space-y-2">
            <div className="flex gap-2">
              <input
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendReply()}
                placeholder="Responder como atendente..."
                className="flex-1 bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone text-sm focus:outline-none focus:border-gold"
              />
              <button onClick={sendReply} disabled={sending || !reply.trim()}
                className="bg-gold hover:bg-gold/90 disabled:opacity-50 text-cream font-bold px-4 py-2 rounded-lg text-sm">
                <Send size={14} />
              </button>
            </div>
            {replyErr && <p className="text-red-400 text-xs">{replyErr}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ChatbotConversations() {
  const [convs, setConvs] = useState<ChatbotConversation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [selected, setSelected] = useState<ChatbotConversation | null>(null);
  const [loading, setLoading] = useState(true);

  const load = (p = page, s = status) => {
    setLoading(true);
    chatbotAdminApi.listConversations(s, p)
      .then((r) => { setConvs(r.items); setTotal(r.total); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(page, status); }, [page, status]);

  const STATUS_FILTERS = [
    { value: undefined,    label: "Todas" },
    { value: "aberta",     label: "Abertas" },
    { value: "em_humano",  label: "Humano" },
    { value: "encerrada",  label: "Encerradas" },
  ];

  if (selected) return (
    <ConversationDetail conv={selected} onBack={() => setSelected(null)} onRefresh={() => load(page, status)} />
  );

  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-cream font-bold text-base">Conversas</h3>
        <button onClick={() => load(page, status)} className="text-stone hover:text-parchment transition-colors">
          <RefreshCw size={16} />
        </button>
      </div>

      <div className="flex gap-2">
        {STATUS_FILTERS.map((f) => (
          <button key={String(f.value)} onClick={() => { setStatus(f.value); setPage(1); }}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
              status === f.value ? "bg-gold/20 border-gold text-gold" : "bg-surface-03 border-surface-03 text-stone hover:text-parchment"
            }`}>{f.label}</button>
        ))}
      </div>

      {loading ? (
        <div className="text-stone text-center py-12">Carregando...</div>
      ) : convs.length === 0 ? (
        <p className="text-stone text-sm text-center py-12">Nenhuma conversa encontrada.</p>
      ) : (
        <div className="space-y-2">
          {convs.map((c) => (
            <button key={c.id} onClick={() => setSelected(c)}
              className="w-full bg-surface-02 rounded-xl px-4 py-3 border border-surface-03 hover:border-gold/30 flex items-center gap-3 text-left transition-colors">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium flex-shrink-0 ${STATUS_COLOR[c.status]}`}>
                {STATUS_LABEL[c.status]}
              </span>
              {c.nome_cliente ? (
                <span className="text-cream text-xs font-semibold flex-shrink-0">{c.nome_cliente}</span>
              ) : (
                <span className="text-stone text-xs flex-shrink-0 italic">Visitante</span>
              )}
              <span className="text-stone text-xs flex-shrink-0 hidden sm:inline">{c.pagina_origem || "/"}</span>
              {c.intencao_detectada && (
                <span className="text-parchment text-xs bg-surface-03 px-2 py-0.5 rounded-full hidden sm:inline">{c.intencao_detectada}</span>
              )}
              {c.resumo_conversa && (
                <span className="text-stone text-xs flex-1 truncate">{c.resumo_conversa}</span>
              )}
              <span className="ml-auto text-stone text-xs flex-shrink-0">
                {new Date(c.iniciada_em).toLocaleString("pt-BR")}
              </span>
            </button>
          ))}
        </div>
      )}

      {total > 20 && (
        <div className="flex items-center justify-center gap-4">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
            className="text-stone hover:text-parchment disabled:opacity-40 text-sm">← Anterior</button>
          <span className="text-stone text-xs">Página {page} · {total} total</span>
          <button onClick={() => setPage((p) => p + 1)} disabled={page * 20 >= total}
            className="text-stone hover:text-parchment disabled:opacity-40 text-sm">Próxima →</button>
        </div>
      )}
    </div>
  );
}
