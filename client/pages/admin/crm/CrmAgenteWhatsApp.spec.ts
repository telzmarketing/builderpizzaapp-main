import { describe, expect, it, vi } from "vitest";
import { loadWhatsAppDetailSession } from "./CrmAgenteWhatsApp";

describe("CrmAgenteWhatsApp detail loading", () => {
  it("returns the session and messages before optional guardrails resolve", async () => {
    let resolveGuardrails!: (value: { blocked: boolean }) => void;
    const guardrails = new Promise<{ blocked: boolean }>((resolve) => {
      resolveGuardrails = resolve;
    });
    const onGuardrails = vi.fn();

    const detail = await loadWhatsAppDetailSession(
      async () => ({ id: "session-1", messages: [{ id: "message-1" }] }),
      () => guardrails,
      onGuardrails,
    );

    expect(detail).toEqual({ id: "session-1", messages: [{ id: "message-1" }] });
    expect(onGuardrails).not.toHaveBeenCalled();

    resolveGuardrails({ blocked: false });
    await vi.waitFor(() => expect(onGuardrails).toHaveBeenCalledWith({ blocked: false }));
  });

  it("keeps the session available when guardrails fail", async () => {
    const onGuardrails = vi.fn();

    await expect(loadWhatsAppDetailSession(
      async () => ({ id: "session-2", messages: [{ id: "message-2" }] }),
      async () => {
        throw new Error("guardrails unavailable");
      },
      onGuardrails,
    )).resolves.toEqual({ id: "session-2", messages: [{ id: "message-2" }] });

    await vi.waitFor(() => expect(onGuardrails).toHaveBeenCalledWith(null));
  });
});
