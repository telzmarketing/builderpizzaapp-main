import { apiRequest } from "./api";

export interface ThemeSettings {
  id: string;
  primary: string;
  secondary: string;
  background_main: string;
  background_alt: string;
  background_card: string;
  text_primary: string;
  text_secondary: string;
  text_muted: string;
  status_success: string;
  status_error: string;
  status_warning: string;
  status_info: string;
  border: string;
  interaction_hover: string;
  interaction_active: string;
  interaction_focus: string;
  navbar: string;
  footer: string;
  sidebar: string;
  modal: string;
  overlay: string;
  badge: string;
  tag: string;
  home_banner_background: string;
  updated_at?: string;
}

export const DEFAULT_THEME: ThemeSettings = {
  id: "default",
  primary:            "#f97316",
  secondary:          "#2d3d56",
  background_main:    "#0c1220",
  background_alt:     "#111827",
  background_card:    "#1e2a3b",
  text_primary:       "#f8fafc",
  text_secondary:     "#e2e8f0",
  text_muted:         "#94a3b8",
  status_success:     "#22c55e",
  status_error:       "#ef4444",
  status_warning:     "#f59e0b",
  status_info:        "#3b82f6",
  border:             "#2d3d56",
  interaction_hover:  "#fb923c",
  interaction_active: "#ea6f10",
  interaction_focus:  "#f97316",
  navbar:             "#111827",
  footer:             "#0c1220",
  sidebar:            "#111827",
  modal:              "#1e2a3b",
  overlay:            "#000000",
  badge:              "#f97316",
  tag:                "#2d3d56",
  home_banner_background: "#1f2937",
};

const THEME_CACHE_KEY = "moschettieri_theme_settings";

function isThemeSettings(value: unknown): value is ThemeSettings {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Record<keyof ThemeSettings, unknown>>;
  return (
    typeof candidate.primary === "string" &&
    typeof candidate.secondary === "string" &&
    typeof candidate.background_main === "string" &&
    typeof candidate.background_alt === "string" &&
    typeof candidate.background_card === "string" &&
    typeof candidate.text_primary === "string" &&
    typeof candidate.text_secondary === "string" &&
    typeof candidate.text_muted === "string"
  );
}

export function readCachedTheme(): ThemeSettings | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(THEME_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!isThemeSettings(parsed)) return null;
    return { ...DEFAULT_THEME, ...parsed };
  } catch {
    return null;
  }
}

export function cacheTheme(t: ThemeSettings): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(THEME_CACHE_KEY, JSON.stringify(t));
  } catch {
    // localStorage can be unavailable in privacy modes; theme still applies in-memory.
  }
}

export const themeApi = {
  async get(): Promise<ThemeSettings> {
    const theme = await apiRequest<ThemeSettings>("GET", "/theme");
    cacheTheme(theme);
    return theme;
  },

  async update(token: string, data: Partial<Omit<ThemeSettings, "id" | "updated_at">>): Promise<ThemeSettings> {
    const theme = await apiRequest<ThemeSettings>("PUT", "/theme", data, { Authorization: `Bearer ${token}` });
    cacheTheme(theme);
    return theme;
  },
};

function hexToHsl(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

export function applyTheme(t: ThemeSettings): void {
  const vars: Record<string, string> = {
    /* ── Raw hex vars ─────────────────────────────── */
    "--color-primary":        t.primary,
    "--color-secondary":      t.secondary,
    "--bg-main":              t.background_main,
    "--bg-alt":               t.background_alt,
    "--bg-card":              t.background_card,
    "--text-primary":         t.text_primary,
    "--text-secondary":       t.text_secondary,
    "--text-muted":           t.text_muted,
    "--status-success":       t.status_success,
    "--status-error":         t.status_error,
    "--status-warning":       t.status_warning,
    "--status-info":          t.status_info,
    "--border-color":         t.border,
    "--interaction-hover":    t.interaction_hover,
    "--interaction-active":   t.interaction_active,
    "--interaction-focus":    t.interaction_focus,
    "--navbar-bg":            t.navbar,
    "--footer-bg":            t.footer,
    "--sidebar-bg":           t.sidebar,
    "--modal-bg":             t.modal,
    "--overlay-bg":           t.overlay,
    "--badge-bg":             t.badge,
    "--tag-bg":               t.tag,
    "--home-banner-bg":       t.home_banner_background,
    /* ── shadcn HSL vars (used by Tailwind tokens) ── */
    "--primary":              hexToHsl(t.primary),
    "--ring":                 hexToHsl(t.primary),
    "--accent":               hexToHsl(t.primary),
    "--background":           hexToHsl(t.background_main),
    "--card":                 hexToHsl(t.background_card),
    "--popover":              hexToHsl(t.background_card),
    "--secondary":            hexToHsl(t.secondary),
    "--border":               hexToHsl(t.border),
    "--input":                hexToHsl(t.border),
    "--sidebar-background":   hexToHsl(t.sidebar),
    "--sidebar-primary":      hexToHsl(t.primary),
    "--sidebar-ring":         hexToHsl(t.primary),
  };

  const css = `:root {\n${Object.entries(vars).map(([k, v]) => `  ${k}: ${v};`).join("\n")}\n}`;
  let style = document.getElementById("theme-override") as HTMLStyleElement | null;
  if (!style) {
    style = document.createElement("style");
    style.id = "theme-override";
    document.head.appendChild(style);
  }
  style.textContent = css;
}
