import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { configureBiMobileWorker, configureMotoboyWorker, configurePwaWorker, consumePwaContextTarget, getPwaApp, getPwaEntryApp, isBiMobilePath, isMotoboyPath, isPwaEntryPath, KDS_PWA_KEYS, PWA_CONTEXT_STORAGE_KEY, pwaScopeForPath, readPwaContext, rememberPwaContext, resolveAdminLoginTarget } from "./motoboyPwa";
import { canShowPwaInstallButton, detectPwaInstallPlatform, hasRecordedPwaInstallation, PWA_INSTALL_DELAY_MS } from "@/components/PwaInstallButton";

const origin = "https://pizza.example";
function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}
function registration(scope = "/", script = "/sw.js", subscribed = false) {
  return {
    scope: origin + scope, active: { scriptURL: origin + script },
    update: vi.fn().mockResolvedValue(undefined), unregister: vi.fn().mockResolvedValue(true),
    pushManager: { getSubscription: vi.fn().mockResolvedValue(subscribed ? { endpoint: "preserve-existing-endpoint" } : null) },
  };
}

describe("Motoboy installation ownership", () => {
  it.each(["/painel", "/motoboy-falso"])("never registers on non-PWA %s", async (path) => {
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
    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope: "/", updateViaCache: "none" });
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
    expect(nodes.find((node) => node.rel === "manifest")?.href).toBe("/api/site-config/manifest.webmanifest?app=storefront");
    window.updateMotoboyPwaHead!("/motoboy/");
    expect(nodes.find((node) => node.rel === "manifest")?.href).toBe("/api/site-config/manifest.webmanifest?app=motoboy");
    window.updateMotoboyPwaHead!("/operacoes/print-pedido/");
    expect(nodes.find((node) => node.rel === "manifest")?.href).toBe("/api/site-config/manifest.webmanifest?app=print-pedido");
    window.updateMotoboyPwaHead!("/checkout");
    expect(nodes.find((node) => node.rel === "manifest")?.href).toBe("/api/site-config/manifest.webmanifest?app=storefront");
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

describe("KDS PWA entries", () => {
  it("persists a safe KDS route through login and consumes it once", () => {
    const storage = memoryStorage();

    expect(rememberPwaContext("/painel/kds/pdv", "?station=front", "#orders", storage)).toBe("/painel/kds/pdv?station=front#orders");
    expect(readPwaContext(storage)).toEqual({
      appKey: "kds-pdv",
      pathname: "/painel/kds/pdv",
      search: "?station=front",
      hash: "#orders",
    });
    expect(consumePwaContextTarget(storage)).toBe("/painel/kds/pdv?station=front#orders");
    expect(storage.getItem(PWA_CONTEXT_STORAGE_KEY)).toBeNull();
    expect(consumePwaContextTarget(storage)).toBeNull();
  });

  it("persists the BI Mobile route through admin login", () => {
    const storage = memoryStorage();

    expect(rememberPwaContext("/painel/bi-mobile", "?period=today", "#revenue", storage))
      .toBe("/painel/bi-mobile?period=today#revenue");
    expect(readPwaContext(storage)).toEqual({
      appKey: "bi-mobile",
      pathname: "/painel/bi-mobile",
      search: "?period=today",
      hash: "#revenue",
    });
    expect(consumePwaContextTarget(storage)).toBe("/painel/bi-mobile?period=today#revenue");
    expect(storage.getItem(PWA_CONTEXT_STORAGE_KEY)).toBeNull();
  });

  it("prefers a PWA route over the platform dashboard after admin login", () => {
    const storage = memoryStorage();
    rememberPwaContext("/painel/bi-mobile", "", "", storage);

    expect(resolveAdminLoginTarget("/painel/plataforma", false, storage)).toBe("/painel/bi-mobile");
    expect(resolveAdminLoginTarget("/painel/plataforma", false, storage)).toBe("/painel/plataforma");
  });

  it("does not persist storefront or arbitrary routes as a login redirect", () => {
    const storage = memoryStorage();

    expect(rememberPwaContext("/painel", "?next=https://example.com", "", storage)).toBeNull();
    expect(storage.getItem(PWA_CONTEXT_STORAGE_KEY)).toBeNull();
  });

  it("maps every dedicated entry and canonical route to its own app key", () => {
    expect(KDS_PWA_KEYS).toEqual([
      "kds-principal", "kds-pizzaiolo", "kds-esfiha", "kds-preparo", "kds-expedicao",
      "kds-motoboys", "kds-pdv", "kds-analitico",
    ]);
    expect(getPwaApp("/app/kds/principal/")?.key).toBe("kds-principal");
    expect(getPwaApp("/painel/kds/analitico")?.key).toBe("kds-analitico");
    expect(getPwaApp("/painel/esfiha")?.key).toBe("kds-esfiha");
    expect(getPwaApp("/app/kds/esfiha")?.scope).toBe("/app/kds/esfiha/");
    expect(getPwaApp("/tv/motoboys")?.key).toBe("kds-motoboys");
    expect(getPwaApp("/painel/kds/pdv")?.scope).toBe("/app/kds/pdv/");
  });

  it("distinguishes dedicated entries from canonical KDS routes", () => {
    expect(getPwaEntryApp("/app/kds/expedicao")?.key).toBe("kds-expedicao");
    expect(isPwaEntryPath("/app/kds/expedicao/queue")).toBe(true);
    expect(getPwaEntryApp("/painel/expedicao")?.key).toBe("kds-expedicao");
    expect(isPwaEntryPath("/tv/motoboys")).toBe(true);
  });

  it("shows the install control on canonical and standalone KDS routes", () => {
    expect(canShowPwaInstallButton("/painel/cozinha", KDS_PWA_KEYS)).toBe(true);
    expect(canShowPwaInstallButton("/app/kds/pizzaiolo/", KDS_PWA_KEYS)).toBe(true);
    expect(canShowPwaInstallButton("/painel/orders", KDS_PWA_KEYS)).toBe(false);
  });

  it("owns an isolated Print Pedido installation boundary", async () => {
    expect(getPwaApp("/operacoes/print-pedido")?.key).toBe("print-pedido");
    expect(canShowPwaInstallButton("/operacoes/print-pedido", ["print-pedido"])).toBe(true);
    const container = { getRegistrations: vi.fn().mockResolvedValue([]), register: vi.fn().mockResolvedValue({}) };
    await configurePwaWorker("/operacoes/print-pedido", container as unknown as ServiceWorkerContainer, origin);
    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope: "/operacoes/print-pedido/", updateViaCache: "none" });
  });

  it("maps public customer URLs to the storefront PWA and registers the root scope", async () => {
    expect(getPwaApp("/")?.key).toBe("storefront");
    expect(getPwaApp("/product/123")?.key).toBe("storefront");
    expect(canShowPwaInstallButton("/cardapio", ["storefront"])).toBe(true);

    const container = { getRegistrations: vi.fn().mockResolvedValue([]), register: vi.fn().mockResolvedValue({}) };
    await configurePwaWorker("/", container as unknown as ServiceWorkerContainer, origin);
    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope: "/", updateViaCache: "none" });
  });

  it("keeps an installed storefront hidden after a page reload", () => {
    const values = new Map<string, string>([["telz:pwa-installed:storefront", "1"]]);
    const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: vi.fn() } as unknown as Storage;
    expect(hasRecordedPwaInstallation("storefront", storage)).toBe(true);
    expect(PWA_INSTALL_DELAY_MS).toBe(60_000);
  });

  it("registers a narrow scope for a dedicated KDS entry", async () => {
    const container = {
      getRegistrations: vi.fn().mockResolvedValue([]),
      register: vi.fn().mockResolvedValue({}),
    };
    await configurePwaWorker("/app/kds/expedicao", container as unknown as ServiceWorkerContainer, origin);
    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope: "/painel/expedicao/", updateViaCache: "none" });
  });

  it.each([
    ["/painel/kds", "/painel/kds/"],
    ["/painel/cozinha", "/painel/cozinha/"],
    ["/painel/esfiha", "/painel/esfiha/"],
    ["/painel/preparo", "/painel/preparo/"],
    ["/painel/expedicao", "/painel/expedicao/"],
    ["/tv/motoboys", "/tv/motoboys/"],
    ["/painel/kds/pdv", "/painel/kds/pdv/"],
    ["/painel/kds/analitico", "/painel/kds/analitico/"],
  ])("registers an isolated scope from operational KDS route %s", async (path, scope) => {
    const container = { getRegistrations: vi.fn().mockResolvedValue([]), register: vi.fn().mockResolvedValue({}) };
    await configurePwaWorker(path, container as unknown as ServiceWorkerContainer, origin);
    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope, updateViaCache: "none" });
  });

  it("keeps nested aliases more specific than the principal KDS alias", () => {
    expect(getPwaApp("/painel/kds/pdv/orders")?.key).toBe("kds-pdv");
    expect(pwaScopeForPath("/painel/kds/pdv/orders")).toBe("/painel/kds/pdv/");
    expect(pwaScopeForPath("/painel/kds/orders")).toBe("/painel/kds/");
  });

  it("keeps the existing Motoboy and BI canonical entry behavior", async () => {
    const motoboyContainer = { getRegistrations: vi.fn().mockResolvedValue([]), register: vi.fn().mockResolvedValue({}) };
    await configurePwaWorker("/motoboy", motoboyContainer as unknown as ServiceWorkerContainer, origin);
    expect(motoboyContainer.register).toHaveBeenCalledWith("/sw.js", { scope: "/motoboy/", updateViaCache: "none" });

    const biContainer = { getRegistrations: vi.fn().mockResolvedValue([]), register: vi.fn().mockResolvedValue({}) };
    await configurePwaWorker("/painel/bi-mobile", biContainer as unknown as ServiceWorkerContainer, origin);
    expect(biContainer.register).toHaveBeenCalledWith("/sw.js", { scope: "/painel/bi-mobile/", updateViaCache: "none" });
  });
});

describe("Print Pedido PWA entry", () => {
  it("owns only the Print Pedido route and its dedicated scope", () => {
    expect(getPwaApp("/operacoes/print-pedido")?.key).toBe("print-pedido");
    expect(getPwaEntryApp("/operacoes/print-pedido/")?.key).toBe("print-pedido");
    expect(pwaScopeForPath("/operacoes/print-pedido")).toBe("/operacoes/print-pedido/");
    expect(canShowPwaInstallButton("/operacoes/print-pedido", ["print-pedido"])).toBe(true);
    expect(canShowPwaInstallButton("/painel/orders", ["print-pedido"])).toBe(false);
  });

  it("registers the worker only inside the Print Pedido scope", async () => {
    const container = { getRegistrations: vi.fn().mockResolvedValue([]), register: vi.fn().mockResolvedValue({}) };

    await configurePwaWorker("/operacoes/print-pedido", container as unknown as ServiceWorkerContainer, origin);

    expect(container.register).toHaveBeenCalledWith("/sw.js", { scope: "/operacoes/print-pedido/", updateViaCache: "none" });
  });
});

describe("PWA install platform detection", () => {
  it.each([
    ["Android Chrome", "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36", "Linux armv8l", 5, "android"],
    ["iPhone Safari", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1", "iPhone", 5, "ios"],
    ["iPad Safari", "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1", "iPad", 5, "ios"],
    ["iPadOS desktop mode", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15", "MacIntel", 5, "ios"],
    ["desktop Chrome", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36", "Win32", 0, "desktop"],
  ])("detects %s without showing iOS instructions on other platforms", (_name, userAgent, platform, maxTouchPoints, expected) => {
    expect(detectPwaInstallPlatform({ userAgent, platform, maxTouchPoints } as Navigator)).toBe(expected);
  });

});
