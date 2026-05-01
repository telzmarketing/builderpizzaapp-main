/**
 * API client do chatbot — segue o mesmo padrão de api.ts.
 */

import { apiRequest } from "./api";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(method, path, body);
}

const get  = <T>(p: string)              => req<T>("GET",    p);
const post = <T>(p: string, b: unknown)  => req<T>("POST",   p, b);
const put  = <T>(p: string, b: unknown)  => req<T>("PUT",    p, b);
const patch= <T>(p: string, b: unknown)  => req<T>("PATCH",  p, b);
const del  = <T>(p: string)              => req<T>("DELETE",  p);

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ChatbotSettings {
  id: string;
  ativo: boolean;
  ia_ativo: boolean;
  nome_bot: string;
  mensagem_inicial: string;
  cor_primaria: string;
  posicao_widget: "bottom-right" | "bottom-left";
  horario_funcionamento: string | null;
  mensagem_fora_horario: string;
  tempo_disparo_auto: number;
  fallback_humano_ativo: boolean;
  provedor_ia: "claude" | "openai";
  modelo_ia: string;
  temperatura: number;
  max_tokens: number;
  prompt_base: string;
  regras_fixas: string;
  tom_de_voz: string;
  objetivo: string;
  instrucoes_transferencia: string;
  limitacoes_proibicoes: string;
  updated_at: string | null;
}

export interface ChatbotAIStatus {
  claude: boolean;
  openai: boolean;
  ativo: boolean;
  using_fallback_provider: boolean;
  openai_key_preview: string | null;
  anthropic_key_preview: string | null;
}

export interface ChatbotFAQ {
  id: string;
  pergunta: string;
  resposta: string;
  categoria: string;
  prioridade: number;
  ativo: boolean;
  vinculo_produto_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatbotAutomation {
  id: string;
  nome: string;
  gatilho: "tempo_na_pagina" | "pagina_especifica" | "carrinho_abandonado" | "produto_visualizado";
  condicao: string;
  mensagem: string;
  ativo: boolean;
  prioridade: number;
  created_at: string;
  updated_at: string;
}

export interface ChatbotKnowledgeDoc {
  id: string;
  titulo: string;
  conteudo: string;
  tipo: string;
  ativo: boolean;
  created_at: string;
  updated_at: string;
}

export interface ChatbotMessage {
  id: string;
  conversation_id: string;
  sender: "visitor" | "bot" | "human";
  mensagem: string;
  tipo: "text" | "action" | "system";
  tokens_consumidos: number | null;
  provedor_usado: string | null;
  latencia_ms: number | null;
  contexto_usado: string | null;
  timestamp: string;
}

export interface ChatbotConversation {
  id: string;
  session_id: string;
  cliente_id: string | null;
  nome_cliente: string | null;
  pagina_origem: string | null;
  status: "aberta" | "em_humano" | "encerrada";
  tags: string | null;
  iniciada_em: string;
  encerrada_em: string | null;
  assumida_por_user_id: string | null;
  intencao_detectada: string | null;
  resumo_conversa: string | null;
  messages?: ChatbotMessage[];
}

export interface ChatbotAnalytics {
  total_hoje: number;
  total_semana: number;
  total_mes: number;
  abertas: number;
  em_humano: number;
  encerradas: number;
  tempo_medio_resposta_ms: number | null;
  tokens_total_mes: number;
  custo_estimado_mes: number;
}

export interface ConversationList {
  total: number;
  page: number;
  page_size: number;
  items: ChatbotConversation[];
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const chatbotAdminApi = {
  // Settings
  getSettings:      ()                       => get<ChatbotSettings>("/admin/chatbot/settings"),
  updateSettings:   (d: Partial<ChatbotSettings>) => put<ChatbotSettings>("/admin/chatbot/settings", d),
  aiStatus:         ()                       => get<ChatbotAIStatus>("/admin/chatbot/settings/ai-status"),
  updateAIKeys:      (d: { openai_api_key?: string; anthropic_api_key?: string }) =>
    put<ChatbotAIStatus>("/admin/chatbot/settings/ai-keys", d),
  testAI:           ()                       => post<{ resposta: string; latencia_ms: number; tokens: number }>("/admin/chatbot/settings/test-ai", {}),

  // FAQ
  listFAQ:          ()                       => get<ChatbotFAQ[]>("/admin/chatbot/faq"),
  createFAQ:        (d: Partial<ChatbotFAQ>) => post<ChatbotFAQ>("/admin/chatbot/faq", d),
  updateFAQ:        (id: string, d: Partial<ChatbotFAQ>) => put<ChatbotFAQ>(`/admin/chatbot/faq/${id}`, d),
  deleteFAQ:        (id: string)             => del<void>(`/admin/chatbot/faq/${id}`),

  // Automations
  listAutomations:  ()                       => get<ChatbotAutomation[]>("/admin/chatbot/automations"),
  createAutomation: (d: Partial<ChatbotAutomation>) => post<ChatbotAutomation>("/admin/chatbot/automations", d),
  updateAutomation: (id: string, d: Partial<ChatbotAutomation>) => put<ChatbotAutomation>(`/admin/chatbot/automations/${id}`, d),
  deleteAutomation: (id: string)             => del<void>(`/admin/chatbot/automations/${id}`),

  // Knowledge
  listKnowledge:    ()                       => get<ChatbotKnowledgeDoc[]>("/admin/chatbot/knowledge"),
  createKnowledge:  (d: Partial<ChatbotKnowledgeDoc>) => post<ChatbotKnowledgeDoc>("/admin/chatbot/knowledge", d),
  updateKnowledge:  (id: string, d: Partial<ChatbotKnowledgeDoc>) => put<ChatbotKnowledgeDoc>(`/admin/chatbot/knowledge/${id}`, d),
  deleteKnowledge:  (id: string)             => del<void>(`/admin/chatbot/knowledge/${id}`),

  // Conversations
  listConversations: (status?: string, page = 1) =>
    get<ConversationList>(`/admin/chatbot/conversations?page=${page}${status ? `&status=${status}` : ""}`),
  getConversation:  (id: string)             => get<ChatbotConversation>(`/admin/chatbot/conversations/${id}`),
  takeover:         (id: string, motivo?: string) => post<ChatbotConversation>(`/admin/chatbot/conversations/${id}/takeover`, { motivo }),
  reply:            (id: string, mensagem: string) => post<ChatbotMessage>(`/admin/chatbot/conversations/${id}/reply`, { mensagem }),
  closeConv:        (id: string)             => post<ChatbotConversation>(`/admin/chatbot/conversations/${id}/close`, {}),
  returnToBot:      (id: string)             => post<ChatbotConversation>(`/admin/chatbot/conversations/${id}/return-to-bot`, {}),
  updateTags:       (id: string, tags: string[]) => patch<void>(`/admin/chatbot/conversations/${id}/tags`, { tags }),

  // Analytics
  analytics:        ()                       => get<ChatbotAnalytics>("/admin/chatbot/analytics"),
};

export interface PublicAutomation {
  gatilho:   "tempo_na_pagina" | "pagina_especifica" | "carrinho_abandonado" | "produto_visualizado";
  condicao:  string;
  mensagem:  string;
  prioridade: number;
}

// Widget public API (used by ChatbotWidget)
export const chatbotPublicApi = {
  config:      ()                               => get<ChatbotSettings>("/chatbot/config"),
  automations: ()                               => get<PublicAutomation[]>("/chatbot/automations"),
  session:     (body: Record<string, unknown>)  => post<{ session_id: string; config: ChatbotSettings }>("/chatbot/session", body),
  message:     (body: Record<string, unknown>)  => post<{ session_id: string; resposta: string; awaiting_human: boolean; fora_do_horario: boolean }>("/chatbot/message", body),
  history:     (sessionId: string)              => get<{ session_id: string; status: string; messages: ChatbotMessage[] }>(`/chatbot/history/${sessionId}`),
  close:       (sessionId: string)              => post<void>("/chatbot/close", { session_id: sessionId }),
};
