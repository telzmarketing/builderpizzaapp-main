import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { configureBiMobileWorker, configureMotoboyWorker, isBiMobilePath, isMotoboyPath } from "./motoboyPwa";

const origin = "https://pizza.example";
function registration(scope = "/", script = "/sw.js", subscribed = false) {
  return {
    scope: origin + scope, active: { scriptURL: origin + script },
    update: vi.fn().mockResolvedValue(undefined), unregister: vi.fn().mockResolvedValue(true),
    pushManager: { getSubscription: vi.fn().mockResolvedValue(subscribed ? { endpoint: "preserve-existing-endpoint" } : null) },
  };
}

describe("Motoboy installation ownership", () => {
  it.each(["/", "/checkout", "/painel", "/painel/cozinha", "/painel/expedicao", "/tv/motoboys", "/motoboy-falso"])("never registers on %s", async (path) => {
    expect(isMotoboyPath(path)).toBe(false);
    const container = { getRegistrations: vi.fn().mockResolvedValue([]), register: vi.fn() };
    await configureMotoboyWorker(path, container as unknown as ServiceWorkerContainer, origin);
    expect(container.register).not.toHaveBeenCalled();
  });

  it("uses a narrow scope and preserves unrelated workers", async () => {
    const legacy = registration();
    const unrelated = registration("/other/", "/other/sw.js");
    const container = { getRegistrations: vi.fn().mockResolvedValue([legacy, unrelated]), register: vi.fn().mockResolvedValue({}) };
    await configureMotoboyWorker("/motoboy/", container as unknown as ServiceWorkerContainer, origin);
    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope: "/motoboy/", updateViaCache: "none" });
    expect(legacy.update).toHaveBeenCalledOnce();
    expect(legacy.unregister).toHaveBeenCalledOnce();
    expect(unrelated.update).not.toHaveBeenCalled();
    expect(unrelated.unregister).not.toHaveBeenCalled();
  });

  it("preserves a subscribed root bridge rather than losing its push endpoint", async () => {
    const legacy = registration("/", "/sw.js", true);
    const container = { getRegistrations: vi.fn().mockResolvedValue([legacy]), register: vi.fn() };
    await configureMotoboyWorker("/", container as unknown as ServiceWorkerContainer, origin);
    expect(legacy.update).toHaveBeenCalledOnce();
    expect(legacy.unregister).not.toHaveBeenCalled();
  });

  it("associates metadata before React only on Motoboy and removes it on SPA exit", () => {
    const nodes: Record<string, string>[] = [];
    const document = {
      querySelectorAll: () => nodes.map((node) => ({ remove: () => nodes.splice(nodes.indexOf(node), 1) })),
      createElement: () => { const attributes: Record<string, string> = {}; return { setAttribute: (key: string, value: string) => { attributes[key] = value; }, attributes }; },
      head: { appendChild: (node: { attributes: Record<string, string> }) => nodes.push(node.attributes) },
    };
    const window = { location: { pathname: "/", search: "", hash: "", replace: vi.fn() }, updateMotoboyPwaHead: undefined as undefined | ((path: string) => void) };
    vm.runInNewContext(readFileSync("public/motoboy-pwa-head.js", "utf8"), { window, document });
    expect(nodes).toHaveLength(0);
    window.updateMotoboyPwaHead!("/motoboy/");
    expect(nodes.find((node) => node.rel === "manifest")?.href).toBe("/api/site-config/manifest.webmanifest");
    window.updateMotoboyPwaHead!("/checkout");
    expect(nodes).toHaveLength(0);
  });
});

describe("BI Mobile installation ownership", () => {
  it("recognizes only the BI Mobile scope", () => {
    expect(isBiMobilePath("/painel/bi-mobile")).toBe(true);
    expect(isBiMobilePath("/painel/bi-mobile/")).toBe(true);
    expect(isBiMobilePath("/painel/bi")).toBe(false);
  });

  it("registers the existing worker with a narrow BI scope", async () => {
    const container = { register: vi.fn().mockResolvedValue({}) };
    await configureBiMobileWorker("/painel/bi-mobile", container as unknown as ServiceWorkerContainer);
    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope: "/painel/bi-mobile/", updateViaCache: "none" });
  });

  it("associates the BI manifest with the BI route only", () => {
    const nodes: Record<string, string>[] = [];
    const document = {
      querySelectorAll: () => nodes.map((node) => ({ remove: () => nodes.splice(nodes.indexOf(node), 1) })),
      createElement: () => { const attributes: Record<string, string> = {}; return { setAttribute: (key: string, value: string) => { attributes[key] = value; }, attributes }; },
      head: { appendChild: (node: { attributes: Record<string, string> }) => nodes.push(node.attributes) },
    };
    const window = { location: { pathname: "/painel/bi-mobile", search: "", hash: "", replace: vi.fn() }, updateMotoboyPwaHead: undefined as undefined | ((path: string) => void) };
    vm.runInNewContext(readFileSync("public/motoboy-pwa-head.js", "utf8"), { window, document });
    window.updateMotoboyPwaHead!("/painel/bi-mobile");
    expect(nodes.find((node) => node.rel === "manifest")?.href).toBe("/api/site-config/manifest.webmanifest?app=bi-mobile");
    expect(nodes.find((node) => node.name === "apple-mobile-web-app-title")?.content).toBe("BI Mobile");
  });
});
