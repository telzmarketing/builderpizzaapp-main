import { describe, expect, it } from "vitest";

import type { ApiPlatformRolloutFlag } from "@/lib/api";
import {
  groupPlatformRolloutFlags,
  platformJwtSecretStateLabel,
  platformRolloutCategoryLabel,
  platformSettingsStatusLabel,
} from "./PlatformSettings";

describe("platform settings read-only presentation", () => {
  it("presents every backend status without inventing a healthy fallback", () => {
    expect(platformSettingsStatusLabel("ok")).toBe("Saudavel");
    expect(platformSettingsStatusLabel("attention")).toBe("Requer atencao");
    expect(platformSettingsStatusLabel("critical")).toBe("Critico");
  });

  it("reports only the JWT configuration state returned by the backend", () => {
    expect(platformJwtSecretStateLabel("configured")).toBe("Configurado");
    expect(platformJwtSecretStateLabel("default")).toBe("Padrao inseguro");
    expect(platformJwtSecretStateLabel("missing")).toBe("Ausente");
  });

  it("groups the allowlisted rollout flags without changing their state or labels", () => {
    const flags: ApiPlatformRolloutFlag[] = [
      { key: "tenant_auth", label: "Autenticacao", enabled: true, category: "access" },
      { key: "tenant_domains", label: "Dominios", enabled: false, category: "access" },
      { key: "tenant_jobs", label: "Jobs", enabled: false, category: "runtime" },
    ];

    expect(groupPlatformRolloutFlags(flags)).toEqual([
      { category: "access", flags: [flags[0], flags[1]] },
      { category: "runtime", flags: [flags[2]] },
    ]);
  });

  it("presents the typed rollout categories without changing their meaning", () => {
    expect(platformRolloutCategoryLabel("isolation")).toBe("Isolamento");
    expect(platformRolloutCategoryLabel("runtime")).toBe("Runtime");
    expect(platformRolloutCategoryLabel("security")).toBe("Seguranca");
    expect(platformRolloutCategoryLabel("access")).toBe("Acesso");
    expect(platformRolloutCategoryLabel("future")).toBe("Outros");
  });
});
