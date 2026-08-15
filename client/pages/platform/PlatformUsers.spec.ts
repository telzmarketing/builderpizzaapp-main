import { describe, expect, it } from "vitest";
import { buildPlatformUsersQuery, type ApiPlatformUserRole } from "../../lib/api";
import {
  PLATFORM_USERS_PAGE_SIZE,
  platformUserEffectiveStatus,
  platformUserRoleNames,
} from "./PlatformUsers";

describe("platform users read-only presentation", () => {
  it("serializes the server-side filters and pagination", () => {
    expect(buildPlatformUsersQuery({
      page: 2,
      page_size: PLATFORM_USERS_PAGE_SIZE,
      q: "  ana@example.com  ",
      status: "active",
      role: "platform_admin",
    })).toBe("page=2&page_size=20&q=ana%40example.com&status=active&role=platform_admin");
  });

  it("omits blank optional filters", () => {
    expect(buildPlatformUsersQuery({ page: 1, page_size: 20, q: " ", role: " " }))
      .toBe("page=1&page_size=20");
  });

  it("presents every global role without inventing a fallback", () => {
    const roles: ApiPlatformUserRole[] = [
      { id: "owner", key: "platform_owner", name: "Proprietario", is_system: true },
      { id: "support", key: "platform_support", name: "Suporte", is_system: true },
    ];
    expect(platformUserRoleNames(roles)).toBe("Proprietario, Suporte");
    expect(platformUserRoleNames([])).toBe("Sem papel");
  });

  it("fails closed when active and status disagree", () => {
    expect(platformUserEffectiveStatus({ active: true, status: "active" })).toBe("active");
    expect(platformUserEffectiveStatus({ active: false, status: "active" })).toBe("inactive");
    expect(platformUserEffectiveStatus({ active: true, status: "inactive" })).toBe("inactive");
  });
});
