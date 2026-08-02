export const PLATFORM_SUPPORT_SESSION_KEY = "platform_support_session";

const PLATFORM_SUPPORT_PANEL_PREFIXES = [
  "/painel/gestao/financeiro",
  "/painel/funcionamento",
] as const;

export const PLATFORM_SUPPORT_PERMISSIONS = {
  is_master: false,
  role_id: null,
  role_name: "Suporte temporario",
  modules: {
    finance: { view: true },
    funcionamento: { view: true },
  },
};

export function shouldLoadRegularAdminPermissions(
  supportSession: PlatformSupportSessionState | null,
): boolean {
  return supportSession === null;
}

export interface PlatformSupportSessionState {
  session_id: string;
  tenant_id: string;
  tenant_name: string;
  expires_at: string;
  scoped_token: string;
  master_token: string;
  master_user: string | null;
  master_permissions: string | null;
}

type SessionStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function readPlatformSupportSession(
  storage: Pick<Storage, "getItem"> = sessionStorage,
): PlatformSupportSessionState | null {
  try {
    const raw = storage.getItem(PLATFORM_SUPPORT_SESSION_KEY);
    if (!raw) return null;
    const state = JSON.parse(raw) as PlatformSupportSessionState;
    if (!state.session_id || !state.tenant_id || !state.scoped_token || !state.master_token || !state.expires_at) return null;
    return state;
  } catch {
    return null;
  }
}

export function isPlatformSupportSessionActive(
  state: PlatformSupportSessionState | null,
  now = Date.now(),
): boolean {
  if (!state) return false;
  const expiresAt = Date.parse(state.expires_at);
  return Number.isFinite(expiresAt) && expiresAt > now;
}

export function isPlatformSupportPanelPathAllowed(pathname: string): boolean {
  return PLATFORM_SUPPORT_PANEL_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function platformRequestAccessToken(
  local: Pick<Storage, "getItem"> = localStorage,
  session: Pick<Storage, "getItem"> = sessionStorage,
): string | null {
  return readPlatformSupportSession(session)?.scoped_token ?? local.getItem("admin_token");
}

export function activatePlatformSupportSession(
  data: Omit<PlatformSupportSessionState, "scoped_token" | "master_token" | "master_user" | "master_permissions"> & {
    access_token: string;
  },
  local: SessionStorage = localStorage,
  session: SessionStorage = sessionStorage,
): PlatformSupportSessionState {
  const masterToken = local.getItem("admin_token");
  if (!masterToken) throw new Error("Sessao Master ausente.");
  const state: PlatformSupportSessionState = {
    session_id: data.session_id,
    tenant_id: data.tenant_id,
    tenant_name: data.tenant_name,
    expires_at: data.expires_at,
    scoped_token: data.access_token,
    master_token: masterToken,
    master_user: local.getItem("admin_user"),
    master_permissions: local.getItem("admin_permissions"),
  };
  session.setItem(PLATFORM_SUPPORT_SESSION_KEY, JSON.stringify(state));
  local.removeItem("admin_permissions");
  return state;
}

export function restorePlatformMasterSession(
  local: SessionStorage = localStorage,
  session: SessionStorage = sessionStorage,
): boolean {
  const state = readPlatformSupportSession(session);
  if (!state) return false;
  local.setItem("admin_token", state.master_token);
  if (state.master_user) local.setItem("admin_user", state.master_user);
  else local.removeItem("admin_user");
  if (state.master_permissions) local.setItem("admin_permissions", state.master_permissions);
  else local.removeItem("admin_permissions");
  session.removeItem(PLATFORM_SUPPORT_SESSION_KEY);
  return true;
}

export function clearPlatformSupportSession(session: Pick<Storage, "removeItem"> = sessionStorage): void {
  session.removeItem(PLATFORM_SUPPORT_SESSION_KEY);
}
