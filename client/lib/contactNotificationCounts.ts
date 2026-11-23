import type { ApiAgenteWhatsAppConversation } from "./api";
import type { ChatbotConversation } from "./chatbotApi";

export type ContactChannel = "chatbot" | "whatsapp";

const CONTACT_READ_STATE_PREFIX = "admin:operations-contact:read:";

export type ContactNotificationReadState = {
  opened: Set<string>;
  markers: Map<string, string>;
};

type ContactNotificationReadStatePayload = {
  opened?: unknown;
  markers?: unknown;
};

function storageScope(storage: Pick<Storage, "getItem">): string | null {
  let adminId = "";
  try {
    const admin = JSON.parse(storage.getItem("admin_user") || "null") as { id?: unknown } | null;
    adminId = typeof admin?.id === "string" ? admin.id : "";
  } catch {
    // Ignore malformed session data and fall back to the token scope.
  }

  let tenantId = "";
  try {
    const token = storage.getItem("admin_token");
    const encodedPayload = token?.split(".")[1];
    if (encodedPayload) {
      const normalizedPayload = encodedPayload.replace(/-/g, "+").replace(/_/g, "/");
      const payload = JSON.parse(atob(normalizedPayload.padEnd(Math.ceil(normalizedPayload.length / 4) * 4, "="))) as { tenant_id?: unknown };
      tenantId = typeof payload.tenant_id === "string" ? payload.tenant_id : "";
    }
  } catch {
    // Ignore malformed tokens; the state must never block the panel.
  }

  const scope = [tenantId, adminId].filter(Boolean).join(":");
  return scope ? `${CONTACT_READ_STATE_PREFIX}${scope}` : null;
}

export function loadContactNotificationReadState(
  storage: Pick<Storage, "getItem"> | null = typeof window === "undefined" ? null : window.localStorage,
): ContactNotificationReadState {
  if (!storage) return { opened: new Set(), markers: new Map() };
  const key = storageScope(storage);
  if (!key) return { opened: new Set(), markers: new Map() };
  try {
    const payload = JSON.parse(storage.getItem(key) || "null") as ContactNotificationReadStatePayload | null;
    const opened = new Set((Array.isArray(payload?.opened) ? payload.opened : []).filter((id): id is string => typeof id === "string"));
    const markers = new Map<string, string>();
    if (payload?.markers && typeof payload.markers === "object") {
      Object.entries(payload.markers as Record<string, unknown>).forEach(([id, marker]) => {
        if (typeof marker === "string") markers.set(id, marker);
      });
    }
    return { opened, markers };
  } catch {
    return { opened: new Set(), markers: new Map() };
  }
}

export function saveContactNotificationReadState(
  state: ContactNotificationReadState,
  storage: Pick<Storage, "getItem" | "setItem"> | null = typeof window === "undefined" ? null : window.localStorage,
): void {
  if (!storage) return;
  const key = storageScope(storage);
  if (!key) return;
  try {
    const markers = Object.fromEntries(state.markers.entries());
    storage.setItem(key, JSON.stringify({ opened: [...state.opened].slice(-500), markers }));
  } catch {
    // Persistence is advisory; the in-memory state remains authoritative.
  }
}

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
