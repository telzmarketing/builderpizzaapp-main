import { describe, expect, it } from "vitest";
import { isPendingChatbotConversation } from "./chatbotAttendance";

const conversation = (status: "aberta" | "em_humano" | "encerrada") => ({
  id: status,
  session_id: status,
  cliente_id: null,
  nome_cliente: null,
  pagina_origem: null,
  status,
  tags: null,
  iniciada_em: "2026-11-13T00:00:00Z",
  encerrada_em: null,
  assumida_por_user_id: null,
  intencao_detectada: null,
  resumo_conversa: null,
});

describe("chatbot attendance queue", () => {
  it("keeps bot-open conversations visible", () => {
    expect(isPendingChatbotConversation(conversation("aberta"))).toBe(true);
  });

  it("keeps human-handoff conversations visible", () => {
    expect(isPendingChatbotConversation(conversation("em_humano"))).toBe(true);
  });

  it("does not show closed conversations as pending", () => {
    expect(isPendingChatbotConversation(conversation("encerrada"))).toBe(false);
  });
});
