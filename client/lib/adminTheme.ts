export type AdminTheme = "dark" | "light";

export const ADMIN_THEME_STORAGE_KEY = "telz_admin_theme";

export function readAdminTheme(): AdminTheme {
  if (typeof window === "undefined") return "dark";
  try {
    return window.localStorage.getItem(ADMIN_THEME_STORAGE_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function persistAdminTheme(theme: AdminTheme): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ADMIN_THEME_STORAGE_KEY, theme);
  } catch {
    // A preferência indisponível não impede o uso do painel nesta sessão.
  }
}

export function toggleAdminTheme(theme: AdminTheme): AdminTheme {
  return theme === "dark" ? "light" : "dark";
}
