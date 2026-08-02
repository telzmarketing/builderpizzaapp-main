import { describe, expect, it } from "vitest";
import {
  clearAdminSession,
  consumeAdminPasswordChanged,
  markAdminPasswordChanged,
  mustChangeAdminPassword,
  readStoredAdminSession,
} from "./adminSession";

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
    has: (key: string) => values.has(key),
  };
}

describe("admin session policy", () => {
  it("requires the password flow only when the backend flag is explicit", () => {
    expect(mustChangeAdminPassword({ force_password_change: true })).toBe(true);
    expect(mustChangeAdminPassword({ force_password_change: false })).toBe(false);
    expect(mustChangeAdminPassword(null)).toBe(false);
  });

  it("fails closed for malformed stored profile data", () => {
    expect(readStoredAdminSession(memoryStorage({ admin_user: "invalid-json" }))).toBeNull();
  });

  it("clears every credential-bearing admin key", () => {
    const storage = memoryStorage({
      admin_token: "token",
      admin_user: "{}",
      admin_permissions: "{}",
    });
    const supportStorage = memoryStorage({ platform_support_session: "{}" });
    clearAdminSession(storage, supportStorage);
    expect(storage.has("admin_token")).toBe(false);
    expect(storage.has("admin_user")).toBe(false);
    expect(storage.has("admin_permissions")).toBe(false);
    expect(supportStorage.has("platform_support_session")).toBe(false);
  });

  it("shows the relogin notice only once after a successful forced change", () => {
    const storage = memoryStorage();
    markAdminPasswordChanged(storage);
    expect(consumeAdminPasswordChanged(storage)).toBe(true);
    expect(consumeAdminPasswordChanged(storage)).toBe(false);
  });
});
