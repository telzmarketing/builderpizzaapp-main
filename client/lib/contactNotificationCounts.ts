import type { ApiAgenteWhatsAppConversation } from "./api";
import type { ChatbotConversation } from "./chatbotApi";

export type ContactChannel = "chatbot" | "whatsapp";

export function contactConversationKey(channel: ContactChannel, id: string): string {
  return `${channel}:${id}`;
}

export function isContactConversationUnread(
  channel: "chatbot",
  conversation: ChatbotConversation,
  opened: ReadonlySet<string>,
): boolean;
export function isContactConversationUnread(
  channel: "whatsapp",
  conversation: ApiAgenteWhatsAppConversation,
  opened: ReadonlySet<string>,
): boolean;
export function isContactConversationUnread(
  channel: ContactChannel,
  conversation: ChatbotConversation | ApiAgenteWhatsAppConversation,
  opened: ReadonlySet<string>,
): boolean {
  if (opened.has(contactConversationKey(channel, conversation.id))) return false;
  if (channel === "whatsapp") {
    return (conversation as ApiAgenteWhatsAppConversation).unread_count > 0;
  }
  return (conversation as ChatbotConversation).status !== "encerrada";
}

export function pendingChatbotConversations(
  conversations: ChatbotConversation[],
  opened: ReadonlySet<string>,
): ChatbotConversation[] {
  return conversations.filter((conversation) => isContactConversationUnread("chatbot", conversation, opened));
}

export function pendingWhatsAppConversations(
  conversations: ApiAgenteWhatsAppConversation[],
  opened: ReadonlySet<string>,
): ApiAgenteWhatsAppConversation[] {
  return conversations.filter((conversation) => isContactConversationUnread("whatsapp", conversation, opened));
}
