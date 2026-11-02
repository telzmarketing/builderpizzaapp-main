import { afterEach, describe, expect, it, vi } from "vitest";
import { notifyOrderArchived, onOrderArchived } from "./orderArchive";

describe("order archive notifications", () => {
  afterEach(() => vi.unstubAllGlobals());

  function setupBrowserStubs() {
    vi.stubGlobal("window", new EventTarget());
    vi.stubGlobal("localStorage", { setItem: vi.fn() });
  }

  it("notifies the current tab after an order is archived", () => {
    setupBrowserStubs();
    const callback = vi.fn();
    const unsubscribe = onOrderArchived(callback);

    notifyOrderArchived("order-1");

    expect(callback).toHaveBeenCalledWith(expect.objectContaining({ orderId: "order-1" }));
    unsubscribe();
  });

  it("stops notifying after unsubscribe", () => {
    setupBrowserStubs();
    const callback = vi.fn();
    const unsubscribe = onOrderArchived(callback);
    unsubscribe();

    notifyOrderArchived("order-2");

    expect(callback).not.toHaveBeenCalled();
  });
});
