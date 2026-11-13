import { Bot, UserCheck } from "lucide-react";
import type { ApiAgenteWhatsAppSession } from "@/lib/api";
import { whatsappAttendance } from "@/lib/whatsappAttendance";

type Session = Pick<ApiAgenteWhatsAppSession, "status" | "ai_enabled" | "automation_blocked">;

export function WhatsAppAttendanceBadge({ session }: { session: Session }) {
  const attendance = whatsappAttendance(session);
  return <span className={`inline-flex rounded-full border px-2 py-1 text-xs ${attendance.canSendHuman ? "border-blue-500/30 bg-blue-500/10 text-blue-300" : "border-amber-500/30 bg-amber-500/10 text-amber-200"}`}>
    {attendance.label}
  </span>;
}

export default function WhatsAppAttendanceControls({ session, busy, onAssume, onReturnToAI }: {
  session: Session;
  busy: boolean;
  onAssume: () => void;
  onReturnToAI: () => void;
}) {
  const attendance = whatsappAttendance(session);
  return <div className="space-y-2" aria-live="polite">
    <WhatsAppAttendanceBadge session={session} />
    <p className="text-xs text-stone">{attendance.canSendHuman
      ? "Você pode responder. A IA permanece desativada até devolver a conversa."
      : "Para enviar como humano, clique em Assumir e desativar IA."}</p>
    <div className="flex flex-wrap gap-2">
      <button type="button" onClick={onAssume} disabled={busy || attendance.canSendHuman}
        className="inline-flex items-center gap-1 rounded-xl border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-xs font-semibold text-blue-300 disabled:opacity-50">
        <UserCheck size={14} />{busy ? "Atualizando..." : "Assumir e desativar IA"}
      </button>
      <button type="button" onClick={onReturnToAI} disabled={busy || attendance.label === "IA ativa"}
        className="inline-flex items-center gap-1 rounded-xl border border-green-500/30 bg-green-500/10 px-3 py-2 text-xs font-semibold text-green-300 disabled:opacity-50">
        <Bot size={14} />Devolver à IA
      </button>
    </div>
  </div>;
}
