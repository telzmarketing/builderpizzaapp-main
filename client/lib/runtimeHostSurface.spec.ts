import { describe, expect, it } from "vitest";
import {
  isPlatformRuntimeSurface,
  isStoreRuntimeSurface,
  type RuntimeHostSurface,
} from "./runtimeHostSurface";

describe("runtime host surface", () => {
  it("accepts a platform response even when no static frontend hostname matched", () => {
    const response: RuntimeHostSurface = {
      surface: "platform",
      hostname: "app.telz.com.br",
    };

    expect(isPlatformRuntimeSurface(response)).toBe(true);
    expect(isStoreRuntimeSurface(response)).toBe(false);
  });

  it("requires a tenant id before allowing a store surface", () => {
    const response: RuntimeHostSurface = {
      surface: "store",
      hostname: "loja.example.com",
      tenant_id: "tenant-a",
    };

    expect(isPlatformRuntimeSurface(response)).toBe(false);
    expect(isStoreRuntimeSurface(response)).toBe(true);
  });
});
