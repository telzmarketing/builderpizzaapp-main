import { describe, expect, it, vi } from "vitest";
import { readChatbotViewport } from "./chatbotViewport";

describe("chatbot mobile viewport", () => {
  it("uses the visual viewport height when the keyboard reduces the visible area", () => {
    vi.stubGlobal("window", {
      innerHeight: 800,
      visualViewport: { height: 472, offsetTop: 24 },
    });

    expect(readChatbotViewport()).toEqual({ height: 472, offsetTop: 24 });
  });

  it("falls back to the window viewport when visualViewport is unavailable", () => {
    vi.stubGlobal("window", { innerHeight: 640 });

    expect(readChatbotViewport()).toEqual({ height: 640, offsetTop: 0 });
  });
});
