import { afterEach, describe, expect, it, vi } from "vitest";
import { agenteWhatsAppApi, type ApiAgenteWhatsAppSession, type ApiAgenteWhatsAppMessage } from "./api";
import { whatsappAttendance } from "./whatsappAttendance";

function session(status: ApiAgenteWhatsAppSession["status"], ai_enabled: boolean, automation_blocked = false): ApiAgenteWhatsAppSession {
  return { id: "session-1", status, ai_enabled, automation_blocked } as ApiAgenteWhatsAppSession;
}

afterEach(() => vi.restoreAllMocks());

describe("WhatsApp human control contract", () => {
  it.each([
    ["open", true], ["open", false], ["waiting_human", false],
    ["waiting_human", true], ["ai_paused", false], ["closed", false], ["human", true],
  ] as const)("blocks manual send for status=%s, ai_enabled=%s", async (status, ai) => {
    vi.spyOn(agenteWhatsAppApi, "getSession").mockResolvedValue({ session: session(status, ai), messages: [] });
    const post = vi.spyOn(agenteWhatsAppApi, "addMessage");
    await expect(agenteWhatsAppApi.sendHumanMessage("session-1", { body: "Olá" })).rejects.toThrow("Assuma a conversa");
    expect(post).not.toHaveBeenCalled();
  });

  it("only queues a manual reply after confirming human control in the API", async () => {
    const get = vi.spyOn(agenteWhatsAppApi, "getSession").mockResolvedValue({ session: session("human", false, true), messages: [] });
    const message = { id: "message-1", provider_status: "queued" } as ApiAgenteWhatsAppMessage;
    const post = vi.spyOn(agenteWhatsAppApi, "addMessage").mockResolvedValue(message);
    await expect(agenteWhatsAppApi.sendHumanMessage("session-1", { body: "Olá" })).resolves.toEqual(message);
    expect(get).toHaveBeenCalledWith("session-1");
    expect(post).toHaveBeenCalledWith("session-1", { body: "Olá", direction: "outbound", sender_type: "human", message_type: "text", provider_status: "queued" });
  });

  it("blocks sending after another screen returns the session to AI", async () => {
    const get = vi.spyOn(agenteWhatsAppApi, "getSession")
      .mockResolvedValueOnce({ session: session("human", false), messages: [] })
      .mockResolvedValueOnce({ session: session("open", true), messages: [] });
    const post = vi.spyOn(agenteWhatsAppApi, "addMessage").mockResolvedValue({} as ApiAgenteWhatsAppMessage);
    await agenteWhatsAppApi.sendHumanMessage("session-1", { body: "Primeira" });
    await expect(agenteWhatsAppApi.sendHumanMessage("session-1", { body: "Segunda" })).rejects.toThrow("Assuma");
    expect(get).toHaveBeenCalledTimes(2);
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("does not POST if control cannot be verified", async () => {
    vi.spyOn(agenteWhatsAppApi, "getSession").mockRejectedValue(new Error("Sem conexão"));
    const post = vi.spyOn(agenteWhatsAppApi, "addMessage");
    await expect(agenteWhatsAppApi.sendHumanMessage("session-1", { body: "Olá" })).rejects.toThrow("Sem conexão");
    expect(post).not.toHaveBeenCalled();
  });

  it("uses the same explicit takeover and return payloads for both screens", async () => {
    const patch = vi.spyOn(agenteWhatsAppApi, "updateSession").mockResolvedValue(session("human", false));
    await agenteWhatsAppApi.assumeSession("session-1");
    expect(patch).toHaveBeenLastCalledWith("session-1", { status: "human", ai_enabled: false, automation_blocked: true });
    await agenteWhatsAppApi.returnSessionToAI("session-1");
    expect(patch).toHaveBeenLastCalledWith("session-1", { status: "open", ai_enabled: true, automation_blocked: false });
  });

  it("does not confuse paused AI or an inconsistent status with human takeover", () => {
    expect(whatsappAttendance(session("ai_paused", false)).canSendHuman).toBe(false);
    expect(whatsappAttendance(session("human", true)).canSendHuman).toBe(false);
    expect(whatsappAttendance(session("open", true, true)).label).not.toBe("IA ativa");
    expect(whatsappAttendance(null).canSendHuman).toBe(false);
    expect(whatsappAttendance(session("human", false)).label).toBe("Humano assumiu · IA desativada");
  });
});
