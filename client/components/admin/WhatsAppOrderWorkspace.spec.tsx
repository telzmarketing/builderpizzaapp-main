import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import WhatsAppOrderWorkspace from "./WhatsAppOrderWorkspace";

describe("customer order workspace", () => {
  it("exposes catalog and order history for a chatbot conversation session", () => {
    const storage = {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
      key: () => null,
      length: 0,
    } as Storage;
    globalThis.localStorage = storage;
    globalThis.sessionStorage = storage;
    globalThis.window = { location: { hostname: "chatbot.test" } } as Window & typeof globalThis;

    const html = renderToStaticMarkup(
      <WhatsAppOrderWorkspace
        session={{ id: "chat-session-1", customer_id: "customer-1", phone: null }}
      />,
    );

    expect(html).toContain("Pedido do cliente");
    expect(html).toContain("Cardápio");
    expect(html).toContain("Histórico");
  });
});
