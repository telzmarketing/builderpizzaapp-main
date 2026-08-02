import { describe, expect, it } from "vitest";
import {
  platformInvitationPasswordError,
  resolvePlatformInvitationToken,
} from "./platformInvitation";

describe("platform invitation helpers", () => {
  it("prefers and trims the path token while supporting the query fallback", () => {
    expect(resolvePlatformInvitationToken(" path-token ", "query-token")).toBe("path-token");
    expect(resolvePlatformInvitationToken(undefined, " query-token ")).toBe("query-token");
    expect(resolvePlatformInvitationToken(undefined, null)).toBe("");
  });

  it("allows an existing account to accept without a password", () => {
    expect(platformInvitationPasswordError("", "")).toBeNull();
  });

  it("blocks partial, short, mismatched, and oversized password pairs", () => {
    expect(platformInvitationPasswordError("", "confirmation")).toMatch(/pelo menos/);
    expect(platformInvitationPasswordError("short", "short")).toMatch(/pelo menos/);
    expect(platformInvitationPasswordError("valid-pass", "different")).toMatch(/confirmacao/);
    const longPassword = "x".repeat(73);
    expect(platformInvitationPasswordError(longPassword, longPassword)).toMatch(/maximo/);
    expect(platformInvitationPasswordError("valid-pass", "valid-pass")).toBeNull();
  });
});
