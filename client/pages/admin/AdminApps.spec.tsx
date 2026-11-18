import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PWA_APPS } from "@/lib/motoboyPwa";
import AdminApps from "./AdminApps";

afterEach(() => vi.unstubAllGlobals());

describe("Admin Apps install links", () => {
  it("offers every PWA with an install action in its manifest route", () => {
    vi.stubGlobal("window", { location: { origin: "https://example.test" } });
    const html = renderToStaticMarkup(<AdminApps />);

    for (const app of PWA_APPS) {
      const expectedPath = app.aliasScope ?? app.entryPath;
      expect(html).toContain(`href="${expectedPath}?instalar=1"`);
      expect(html).toContain(`aria-label="Instalar ${app.label}"`);
      expect(html).toContain(`value="https://example.test${expectedPath}?instalar=1"`);
    }
    expect(html).toContain('href="/painel/cozinha/?instalar=1"');
    expect(html).toContain('href="/painel/kds/auditoria/?instalar=1"');
    expect(html).not.toContain('target="_blank"');
    expect(html.match(/aria-label="Instalar /g)).toHaveLength(PWA_APPS.length);
  });
});
