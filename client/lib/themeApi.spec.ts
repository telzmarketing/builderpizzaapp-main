import { afterEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_THEME, getThemeCacheKey, readCachedTheme } from "./themeApi";

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("tenant theme cache", () => {
  it("normalizes the hostname into a tenant-safe cache key", () => {
    expect(getThemeCacheKey(" GRAN.TELZ.COM.BR. ")).toBe("moschettieri_theme_settings:gran.telz.com.br");
  });

  it("does not reuse a cached theme from another hostname", () => {
    const storage = memoryStorage();
    storage.setItem(getThemeCacheKey("empresa-a.example"), JSON.stringify({
      ...DEFAULT_THEME,
      primary: "#123456",
    }));
    vi.stubGlobal("window", { localStorage: storage, location: { hostname: "empresa-b.example" } });

    expect(readCachedTheme()).toBeNull();
  });
});
