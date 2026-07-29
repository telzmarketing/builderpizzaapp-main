const ADMIN_LOGIN_PATH = "/admin/auth/login";

export function shouldInvalidateAdminSession(status: number, path: string): boolean {
  return status === 401 && path !== ADMIN_LOGIN_PATH;
}
