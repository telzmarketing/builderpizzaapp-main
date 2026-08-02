import type { ApiPlatformLicense, ApiPlatformLicenseStatus } from "@/lib/api";

export type PlatformLicenseAction =
  | "renew"
  | "extend"
  | "start_trial"
  | "convert"
  | "courtesy"
  | "grace"
  | "expire"
  | "cancel"
  | "suspend"
  | "block"
  | "reactivate";

export const PLATFORM_LICENSE_ACTION_META: Record<PlatformLicenseAction, {
  label: string;
  destructive?: boolean;
}> = {
  renew: { label: "Renovar" },
  extend: { label: "Prorrogar" },
  start_trial: { label: "Iniciar trial" },
  convert: { label: "Converter trial" },
  courtesy: { label: "Conceder cortesia" },
  grace: { label: "Iniciar carencia" },
  expire: { label: "Expirar agora", destructive: true },
  cancel: { label: "Cancelar", destructive: true },
  suspend: { label: "Suspender", destructive: true },
  block: { label: "Bloquear", destructive: true },
  reactivate: { label: "Reativar" },
};

const ACTIONS_BY_STATUS: Record<ApiPlatformLicenseStatus, PlatformLicenseAction[]> = {
  trial: ["extend", "convert", "courtesy", "expire", "cancel", "suspend", "block"],
  active: ["renew", "extend", "courtesy", "grace", "expire", "cancel", "suspend", "block"],
  grace_period: ["renew", "extend", "courtesy", "expire", "cancel", "suspend", "block"],
  expired: ["renew", "start_trial", "courtesy", "grace", "cancel", "block"],
  suspended: ["renew", "courtesy", "expire", "cancel", "block", "reactivate"],
  blocked: ["renew", "courtesy", "expire", "cancel", "reactivate"],
  cancelled: ["renew", "start_trial", "courtesy"],
};

const DAYS_REQUIRED = new Set<PlatformLicenseAction>([
  "renew",
  "extend",
  "start_trial",
  "courtesy",
  "grace",
]);

export function platformLicenseActionsForStatus(
  status: ApiPlatformLicenseStatus,
): PlatformLicenseAction[] {
  return ACTIONS_BY_STATUS[status];
}

export function platformLicenseActionNeedsDays(
  action: PlatformLicenseAction,
  license: Pick<ApiPlatformLicense, "expires_at">,
  now = Date.now(),
): boolean {
  if (DAYS_REQUIRED.has(action)) return true;
  if (action !== "reactivate" || !license.expires_at) return false;
  const expiresAt = Date.parse(license.expires_at);
  return Number.isFinite(expiresAt) && expiresAt <= now;
}
