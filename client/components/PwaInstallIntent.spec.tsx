import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { PWA_APPS } from "@/lib/motoboyPwa";
import PwaInstallIntent from "./PwaInstallIntent";

function render(path: string) {
  return renderToStaticMarkup(<MemoryRouter initialEntries={[path]}><PwaInstallIntent /></MemoryRouter>);
}

describe("installation intent", () => {
  it.each([
    ["/painel/kds/auditoria/?instalar=1", "kds-auditoria", "KDS Auditoria"],
    ["/painel/bi-mobile/?instalar=1", "bi-mobile", "BI Mobile"],
    ["/motoboy/?instalar=1", "motoboy", "Motoboy"],
  ])("offers installation on %s", (path, key, label) => {
    const markup = render(path);
    expect(markup).toContain(`data-pwa-install-intent="${key}"`);
    expect(markup).toContain(`Instalar ${label}`);
    expect(markup).toContain("A instalação será feita neste dispositivo");
  });

  it("does not add install UI during normal KDS use", () => {
    expect(render("/painel/kds/auditoria/")).toBe("");
  });

  it("offers the correct app from every installation link", () => {
    for (const app of PWA_APPS) {
      const path = app.aliasScope ?? app.entryPath;
      expect(render(`${path}?instalar=1`)).toContain(`data-pwa-install-intent="${app.key}"`);
    }
  });
});
