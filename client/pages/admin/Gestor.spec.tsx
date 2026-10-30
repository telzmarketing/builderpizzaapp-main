import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import Gestor from "./Gestor";

describe("Gestor IA administration surface", () => {
  it("identifies the client AI as a separate module before data loads", () => {
    const html = renderToStaticMarkup(<MemoryRouter><Gestor /></MemoryRouter>);
    expect(html).toContain("Administração exclusiva");
    expect(html).toContain("IA de clientes");
    expect(html).toContain("/painel/crm/agente-whatsapp");
    expect(html).toContain("Identidade / Canais");
    expect(html).not.toContain("Conversas abertas");
  });
});
