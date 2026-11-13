import type { ApiAgenteWhatsAppSession } from "./api";

type AttendanceSession = Pick<ApiAgenteWhatsAppSession, "status" | "ai_enabled" | "automation_blocked">;

export function whatsappAttendance(session: AttendanceSession | null | undefined) {
  if (!session) return { label: "Controle não confirmado", canSendHuman: false };
  if (session.status === "closed") return { label: "Conversa encerrada", canSendHuman: false };
  if (session.status === "human" && session.ai_enabled === false) {
    return { label: "Humano assumiu · IA desativada", canSendHuman: true };
  }
  if (session.status === "open" && session.ai_enabled === true && !session.automation_blocked) {
    return { label: "IA ativa", canSendHuman: false };
  }
  if (session.status === "waiting_human") return { label: "Aguardando humano assumir", canSendHuman: false };
  return { label: "IA pausada · assuma para responder", canSendHuman: false };
}

export function requireWhatsAppHumanAttendance(session: AttendanceSession) {
  if (!whatsappAttendance(session).canSendHuman) {
    throw new Error("Assuma a conversa e desative a IA antes de enviar uma mensagem humana.");
  }
}
