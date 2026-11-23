import { describe, expect, it } from "vitest";
import {
  contactConversationKey,
  isContactConversationUnread,
  loadContactNotificationReadState,
  pendingChatbotConversations,
  pendingWhatsAppConversations,
  saveContactNotificationReadState,
} from "./contactNotificationCounts";

describe("operations contact notification counts", () => {
  it("keeps only chatbot conversations that were not opened", () => {
    const conversations = [
      { id: "chat-1", status: "aberta" },
      { id: "chat-2", status: "em_humano" },
      { id: "chat-3", status: "encerrada" },
    ] as any[];

    expect(
      pendingChatbotConversations(
        conversations,
        new Set([contactConversationKey("chatbot", "chat-1")]),
      ).map((conversation) => conversation.id),
    ).toEqual(["chat-2"]);
  });

  it("counts only unread WhatsApp conversations and removes opened ones", () => {
    const conversations = [
      { id: "wa-1", unread_count: 0 },
      { id: "wa-2", unread_count: 2 },
      { id: "wa-3", unread_count: 1 },
    ] as any[];

    expect(
      pendingWhatsAppConversations(
        conversations,
        new Set([contactConversationKey("whatsapp", "wa-2")]),
      ).map((conversation) => conversation.id),
    ).toEqual(["wa-3"]);
  });

  it("identifies the visual unread state for each channel", () => {
    expect(
      isContactConversationUnread("chatbot", { id: "chat-1", status: "aberta" } as any, new Set()),
    ).toBe(true);
    expect(
      isContactConversationUnread(
        "chatbot",
        { id: "chat-1", status: "aberta" } as any,
        new Set([contactConversationKey("chatbot", "chat-1")]),
      ),
    ).toBe(false);
    expect(
      isContactConversationUnread("whatsapp", { id: "wa-1", unread_count: 1 } as any, new Set()),
    ).toBe(true);
    expect(
      isContactConversationUnread("whatsapp", { id: "wa-1", unread_count: 0 } as any, new Set()),
    ).toBe(false);
  });

  it("persists opened conversations scoped to the logged-in tenant and admin", () => {
    const values = new Map([
      ["admin_user", JSON.stringify({ id: "admin-1" })],
      ["admin_token", "header.eyJ0ZW5hbnRfaWQiOiJ0ZW5hbnQtMSJ9.signature"],
    ]);
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    const key = contactConversationKey("chatbot", "chat-1");
    saveContactNotificationReadState({ opened: new Set([key]), markers: new Map([[key, "marker-1"]]) }, storage);

    const loaded = loadContactNotificationReadState(storage);
    expect(loaded.opened.has(key)).toBe(true);
    expect(loaded.markers.get(key)).toBe("marker-1");
    expect(values.has("admin:operations-contact:read:tenant-1:admin-1")).toBe(true);
  });
});
