import { describe, expect, it } from "vitest";
import {
  platformItemMatchesPath,
  platformNavigationGroups,
} from "./platformNavigation";
import { getPlatformPageMeta } from "./platformPageMeta";

describe("platform master navigation", () => {
  it("exposes paths only for entries backed by real pages", () => {
    const items = platformNavigationGroups.flatMap((group) => group.items);

    expect(items.filter((item) => item.available).every((item) => !!item.path)).toBe(true);
    expect(items.filter((item) => !item.available).every((item) => !item.path)).toBe(true);
  });

  it("keeps company details inside the company navigation item", () => {
    const companies = platformNavigationGroups[0].items.find((item) => item.label === "Empresas");

    expect(companies).toBeDefined();
    expect(platformItemMatchesPath(companies!, "/painel/empresas/tenant-123")).toBe(true);
  });

  it("resolves dynamic company detail metadata", () => {
    const meta = getPlatformPageMeta("/painel/empresas/tenant-123");

    expect(meta.title).toBe("Detalhes da empresa");
    expect(meta.eyebrow).toContain("Empresas");
  });

  it("links billing navigation to the functional billing overview", () => {
    const billing = platformNavigationGroups[0].items.find((item) => item.label === "Cobrancas");

    expect(billing).toMatchObject({ available: true, path: "/painel/cobrancas" });
    expect(getPlatformPageMeta("/painel/cobrancas").title).toBe("Cobrancas");
  });
});
