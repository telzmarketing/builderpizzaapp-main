import { describe, expect, it, vi } from "vitest";
import { loadWhatsAppDetailSession, resolveWhatsAppConversationId } from "./CrmAgenteWhatsApp";

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

describe("CrmAgenteWhatsApp conversation selection", () => {
  const rows = [{ id: "session-1" }, { id: "session-2" }];

  it("keeps a selected conversation that still exists", () => {
    expect(resolveWhatsAppConversationId(rows, null, "session-2")).toBe("session-2");
  });

  it("falls back to the first available conversation when the selected session was deleted", () => {
    expect(resolveWhatsAppConversationId(rows, null, "deleted-session")).toBe("session-1");
  });

  it("clears the selection when there are no conversations", () => {
    expect(resolveWhatsAppConversationId([], null, "deleted-session")).toBeNull();
  });
});
