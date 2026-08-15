import { describe, expect, it } from "vitest";

import type {
  ApiPlatformJobWorker,
  ApiPlatformStorageOverview,
} from "@/lib/api";

import {
  PlatformBackups,
  PlatformErrors,
  PlatformGateway,
  PlatformHealth,
  PlatformIntegrations,
  PlatformJobs,
  PlatformStorage,
  formatPlatformBytes,
  formatPlatformDate,
  formatPlatformDuration,
  loadOperationalParts,
  operationalFreshnessLabel,
  platformOperationalStatusLabel,
  platformWorkerReactKey,
  validatePlatformErrorNote,
} from "./PlatformOperationalPages";

describe("platform operational pages", () => {
  it("exports one real page component for every monitoring route", () => {
    expect([
      PlatformHealth,
      PlatformIntegrations,
      PlatformJobs,
      PlatformGateway,
      PlatformErrors,
      PlatformStorage,
      PlatformBackups,
    ].every((page) => typeof page === "function")).toBe(true);
  });

  it("presents statuses and freshness without treating unknown as healthy", () => {
    expect(platformOperationalStatusLabel("healthy")).toBe("Saudavel");
    expect(platformOperationalStatusLabel("critical")).toBe("Critico");
    expect(platformOperationalStatusLabel("unknown")).toBe("Desconhecido");
    expect(operationalFreshnessLabel(false)).toBe("Dados atuais");
    expect(operationalFreshnessLabel(true)).toBe("Dados desatualizados");
  });

  it("keeps storage health in the typed toolbar contract", () => {
    const overview = {
      status: "critical",
    } satisfies Pick<ApiPlatformStorageOverview, "status">;

    expect(platformOperationalStatusLabel(overview.status)).toBe("Critico");
  });

  it("uses worker and instance identities to distinguish runtime cards", () => {
    const first = {
      key: "agente_whatsapp",
      instance_key: "host-a:123",
    } satisfies Pick<ApiPlatformJobWorker, "key" | "instance_key">;
    const second = {
      key: "agente_whatsapp",
      instance_key: "host-b:456",
    } satisfies Pick<ApiPlatformJobWorker, "key" | "instance_key">;

    expect(platformWorkerReactKey(first)).not.toBe(platformWorkerReactKey(second));
  });

  it("formats operational values and rejects invalid placeholders", () => {
    expect(formatPlatformBytes(0)).toBe("0 B");
    expect(formatPlatformBytes(1024 * 1024)).toBe("1 MB");
    expect(formatPlatformBytes(-1)).toBe("Nao informado");
    expect(formatPlatformDuration(90)).toBe("1 min");
    expect(formatPlatformDuration(null)).toBe("Nao informado");
    expect(formatPlatformDate("not-a-date")).toBe("Nao informado");
  });

  it("requires an auditable note before changing an error disposition", () => {
    expect(validatePlatformErrorNote("")).toContain("ao menos 2 caracteres");
    expect(validatePlatformErrorNote("a")).toContain("ao menos 2 caracteres");
    expect(validatePlatformErrorNote("  incidente confirmado  ")).toBe("");
  });

  it("preserves successful sources and exposes a partial error", async () => {
    const result = await loadOperationalParts<{
      overview: { total: number };
      items: string[];
    }>({
      overview: async () => ({ total: 3 }),
      items: async () => { throw new Error("Itens indisponiveis"); },
    });

    expect(result.values).toEqual({ overview: { total: 3 } });
    expect(result.errors).toEqual(["Itens indisponiveis"]);
  });

  it("fails the page when every operational source is unavailable", async () => {
    await expect(loadOperationalParts<{
      overview: object;
      items: object;
    }>({
      overview: async () => { throw new Error("Resumo indisponivel"); },
      items: async () => { throw new Error("Itens indisponiveis"); },
    })).rejects.toThrow("Resumo indisponivel");
  });
});
