import type { ChatbotConversation } from "./chatbotApi";

/** Conversas que ainda podem aparecer na fila de Atendimento do painel. */
export function isPendingChatbotConversation(conversation: ChatbotConversation): boolean {
  return conversation.status !== "encerrada";
}
