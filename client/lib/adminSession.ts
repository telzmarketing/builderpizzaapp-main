const ADMIN_LOGIN_PATH = "/admin/auth/login";
export const ADMIN_PASSWORD_CHANGED_KEY = "admin_password_changed";

export function shouldInvalidateAdminSession(status: number, path: string): boolean {
  return status === 401 && path !== ADMIN_LOGIN_PATH;
}

export interface StoredAdminSession {
  id?: string;
  email?: string;
  name?: string;
  force_password_change?: boolean;
}

export function readStoredAdminSession(storage: Pick<Storage, "getItem"> = localStorage): StoredAdminSession | null {
  try {
    const raw = storage.getItem("admin_user");
    return raw ? JSON.parse(raw) as StoredAdminSession : null;
  } catch {
    return null;
  }
}

export function mustChangeAdminPassword(admin: StoredAdminSession | null | undefined): boolean {
  return admin?.force_password_change === true;
}

export function markAdminPasswordChanged(
  storage: Pick<Storage, "setItem"> = sessionStorage,
): void {
  storage.setItem(ADMIN_PASSWORD_CHANGED_KEY, "true");
}

export function consumeAdminPasswordChanged(
  storage: Pick<Storage, "getItem" | "removeItem"> = sessionStorage,
): boolean {
  const changed = storage.getItem(ADMIN_PASSWORD_CHANGED_KEY) === "true";
  if (changed) storage.removeItem(ADMIN_PASSWORD_CHANGED_KEY);
  return changed;
}

export function clearAdminSession(
  storage: Pick<Storage, "removeItem"> = localStorage,
  supportStorage: Pick<Storage, "removeItem"> = sessionStorage,
): void {
  storage.removeItem("admin_token");
  storage.removeItem("admin_user");
  storage.removeItem("admin_permissions");
  supportStorage.removeItem("platform_support_session");
}
