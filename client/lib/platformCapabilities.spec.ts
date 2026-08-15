import { describe, expect, it } from "vitest";

import {
  clearPlatformPermissions,
  hasPlatformCapability,
  readPlatformPermissions,
  storePlatformPermissions,
} from "./platformCapabilities";

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}

describe("platform capabilities", () => {
  it("fails closed when cached capabilities are absent or malformed", () => {
    expect(readPlatformPermissions(memoryStorage())).toEqual([]);
    expect(readPlatformPermissions(memoryStorage({ platform_permissions: "invalid" }))).toEqual([]);
    expect(hasPlatformCapability(null, "storage.view")).toBe(false);
    expect(hasPlatformCapability([], "backups.view")).toBe(false);
  });

  it("stores a sanitized list separately from regular admin permissions", () => {
    const storage = memoryStorage({ admin_permissions: "{\"is_master\":true}" });
    expect(storePlatformPermissions([
      "monitoring.view",
      "monitoring.view",
      " storage.view ",
      null,
    ], storage)).toEqual(["monitoring.view", "storage.view"]);
    expect(readPlatformPermissions(storage)).toEqual(["monitoring.view", "storage.view"]);
    expect(storage.getItem("admin_permissions")).toBe("{\"is_master\":true}");
    clearPlatformPermissions(storage);
    expect(readPlatformPermissions(storage)).toEqual([]);
  });

  it("keeps published base pages accessible when no capability is required", () => {
    expect(hasPlatformCapability([], undefined)).toBe(true);
  });
});
