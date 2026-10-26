import { afterEach, describe, expect, it, vi } from "vitest";
import { scheduleShippingQuote } from "./checkoutShipping";

describe("checkout address shipping requests", () => {
  afterEach(() => vi.useRealTimers());
  it("discards the previous quote immediately and ignores a late response for the old address", async () => {
    vi.useFakeTimers();
    let oldResolve!: (value: string) => void;
    let current: string | null = "old fee";
    const callbacks = { result: (value: string | null) => { current = value; }, loading: vi.fn(), error: vi.fn() };
    const cancel = scheduleShippingQuote(() => new Promise<string>((resolve) => { oldResolve = resolve; }), callbacks);
    expect(current).toBeNull();
    await vi.advanceTimersByTimeAsync(600);
    cancel();
    scheduleShippingQuote(async () => "new address fee", callbacks);
    await vi.advanceTimersByTimeAsync(600);
    oldResolve("wrong old address fee");
    await vi.advanceTimersByTimeAsync(0);
    expect(current).toBe("new address fee");
  });
  it("keeps the quote absent on provider failure and supplies an explicit retryable error", async () => {
    vi.useFakeTimers();
    const callbacks = { result: vi.fn(), loading: vi.fn(), error: vi.fn() };
    scheduleShippingQuote(async () => { throw new Error("Shipping unavailable"); }, callbacks);
    await vi.runAllTimersAsync();
    expect(callbacks.result.mock.calls).toEqual([[null]]);
    expect(callbacks.error).toHaveBeenLastCalledWith("Shipping unavailable");
    expect(callbacks.loading).toHaveBeenLastCalledWith(false);
  });
  it("cancels a pending debounce when switching to pickup without calling the delivery API", async () => {
    vi.useFakeTimers();
    const calculate = vi.fn();
    const cancel = scheduleShippingQuote(calculate, { result: vi.fn(), loading: vi.fn(), error: vi.fn() });
    cancel();
    await vi.runAllTimersAsync();
    expect(calculate).not.toHaveBeenCalled();
  });
});
