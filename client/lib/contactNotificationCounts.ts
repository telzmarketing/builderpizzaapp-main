import type { ApiAgenteWhatsAppConversation } from "./api";
import type { ChatbotConversation } from "./chatbotApi";

export type ContactChannel = "chatbot" | "whatsapp";

export function contactConversationKey(channel: ContactChannel, id: string): string {
  return `${channel}:${id}`;
}

export function pendingChatbotConversations(
  conversations: ChatbotConversation[],
  opened: ReadonlySet<string>,
): ChatbotConversation[] {
  return conversations.filter(
    (conversation) =>
      conversation.status !== "encerrada" &&
      !opened.has(contactConversationKey("chatbot", conversation.id)),
  );
}

export function pendingWhatsAppConversations(
  conversations: ApiAgenteWhatsAppConversation[],
  opened: ReadonlySet<string>,
): ApiAgenteWhatsAppConversation[] {
  return conversations.filter(
    (conversation) =>
      conversation.unread_count > 0 &&
      !opened.has(contactConversationKey("whatsapp", conversation.id)),
  );
}
