import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import WhatsAppAttendanceControls from "./WhatsAppAttendanceControls";
import type { ApiAgenteWhatsAppSession } from "@/lib/api";

function render(status: ApiAgenteWhatsAppSession["status"], ai_enabled: boolean, busy = false) {
  return renderToStaticMarkup(<WhatsAppAttendanceControls
    session={{ status, ai_enabled, automation_blocked: false }} busy={busy}
    onAssume={() => {}} onReturnToAI={() => {}} />);
}

describe("shared WhatsApp attendance controls", () => {
  it("shows AI control and the explicit takeover action", () => {
    const html = render("open", true);
    expect(html).toContain("IA ativa");
    expect(html).toContain("Assumir e desativar IA");
    expect(html).toContain("Para enviar como humano");
  });
  it("shows human takeover and that AI remains disabled", () => {
    const html = render("human", false);
    expect(html).toContain("Humano assumiu · IA desativada");
    expect(html).toContain("A IA permanece desativada");
    expect(html).toContain("Devolver à IA");
  });
  it("does not label a paused or closed session as human takeover", () => {
    expect(render("ai_paused", false)).not.toContain("Humano assumiu");
    expect(render("closed", false)).toContain("Conversa encerrada");
  });
  it("disables both actions while the API confirms control", () => {
    expect(render("open", true, true).match(/disabled=""/g)).toHaveLength(2);
  });
});
