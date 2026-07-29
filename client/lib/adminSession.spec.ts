import { describe, expect, it } from "vitest";
import { shouldInvalidateAdminSession } from "./adminSession";

describe("admin session invalidation", () => {
  it("keeps the login screen stable when credentials are rejected", () => {
    expect(shouldInvalidateAdminSession(401, "/admin/auth/login")).toBe(false);
  });

  it("expires a session only when a protected request confirms 401", () => {
    expect(shouldInvalidateAdminSession(401, "/admin/auth/me")).toBe(true);
    expect(shouldInvalidateAdminSession(500, "/admin/auth/me")).toBe(false);
  });
});
