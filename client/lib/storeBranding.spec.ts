import { describe, expect, it } from "vitest";
import { storeBranding } from "./storeBranding";
import { withReceiptBranding, DEFAULT_PRINTER_SETTINGS } from "./printing";

describe("tenant store branding", () => {
  it("uses the configured brand logo before the optional white logo", () => {
    expect(storeBranding({ brand: { name: "Gran Torino", logo: "/uploads/tenant-a/logo.png" }, media: { logoUrl: "/uploads/tenant-a/white.png" } })).toMatchObject({ name: "Gran Torino", logo: expect.stringContaining("/uploads/tenant-a/logo.png") });
  });
  it("supports the existing media logo field when brand logo is absent or textual", () => {
    expect(storeBranding({ brand: { logo: "🍕" }, media: { logoUrl: "/uploads/tenant-b/logo.png" } }).logo).toContain("/uploads/tenant-b/logo.png");
  });
  it("falls back to the actual tenant name without inventing an image", () => {
    expect(storeBranding({ brand: { name: "Loja B" } })).toEqual({ name: "Loja B", tagline: "", logo: "" });
  });
  it("does not keep another store's cached receipt logo when current branding has none", () => {
    expect(withReceiptBranding({ ...DEFAULT_PRINTER_SETTINGS, storeLogoUrl: "https://old.example/logo.png" }, { brand: { name: "Loja B" } })).toMatchObject({ storeName: "Loja B", storeLogoUrl: undefined });
  });
});
