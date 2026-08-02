import type { ApiPlatformModule } from "@/lib/api";

export type PlatformTenantModuleOrigin = "plan" | "addon" | "courtesy" | "trial";

export interface PlatformTenantModuleDraft {
  enabled: boolean;
  origin: PlatformTenantModuleOrigin;
  starts_at: string;
  ends_at: string;
  limit_value: string;
  additional_price: string;
  config_text: string;
}

function toLocalDateTime(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function toIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) throw new Error("Data de disponibilidade invalida.");
  return date.toISOString();
}

export function parsePlatformTenantModuleConfig(value?: string | null): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value || "{}");
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("A configuracao do modulo precisa ser um objeto JSON.");
  }
  return parsed as Record<string, unknown>;
}

export function platformTenantModuleDraft(module: ApiPlatformModule): PlatformTenantModuleDraft {
  const entitlement = module.entitlement;
  let configText = "";
  if (module.module_group !== "integrations") {
    configText = entitlement?.config_json || "{}";
    try {
      configText = JSON.stringify(parsePlatformTenantModuleConfig(configText), null, 2);
    } catch {
      // Preserve malformed persisted data verbatim so saving is blocked instead
      // of silently replacing it with an empty object.
    }
  }
  return {
    enabled: entitlement?.enabled ?? false,
    origin: entitlement?.origin ?? "addon",
    starts_at: toLocalDateTime(entitlement?.starts_at),
    ends_at: toLocalDateTime(entitlement?.ends_at),
    limit_value: entitlement?.limit_value == null ? "" : String(entitlement.limit_value),
    additional_price: String(entitlement?.additional_price ?? 0),
    config_text: configText,
  };
}

export function buildPlatformTenantModulePayload(
  modules: ApiPlatformModule[],
  drafts: Record<string, PlatformTenantModuleDraft>,
  disableReason: string,
) {
  return modules
    .filter((module) => module.entitlement || drafts[module.id]?.enabled)
    .map((module) => {
      const draft = drafts[module.id];
      if (!draft) throw new Error(`Configuracao ausente para o modulo ${module.name}.`);
      const startsAt = toIso(draft.starts_at);
      const endsAt = toIso(draft.ends_at);
      if (startsAt && endsAt && Date.parse(endsAt) <= Date.parse(startsAt)) {
        throw new Error(`O termino de ${module.name} precisa ser posterior ao inicio.`);
      }
      const limitValue = draft.limit_value.trim() === "" ? null : Number(draft.limit_value);
      const additionalPrice = Number(draft.additional_price || 0);
      if (limitValue !== null && (!Number.isInteger(limitValue) || limitValue < 0)) {
        throw new Error(`O limite de ${module.name} precisa ser um inteiro positivo.`);
      }
      if (!Number.isFinite(additionalPrice) || additionalPrice < 0) {
        throw new Error(`O valor adicional de ${module.name} e invalido.`);
      }
      return {
        module_id: module.id,
        enabled: draft.enabled,
        origin: draft.origin,
        ...(startsAt ? { starts_at: startsAt } : {}),
        ends_at: endsAt,
        limit_value: limitValue,
        additional_price: additionalPrice,
        ...(!draft.enabled ? { reason: disableReason } : {}),
        ...(module.module_group === "integrations"
          ? {}
          : { config: parsePlatformTenantModuleConfig(draft.config_text) }),
      };
    });
}
