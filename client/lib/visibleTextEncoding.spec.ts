import { describe, expect, it } from "vitest";
import { repairVisibleText } from "./visibleTextEncoding";

describe("visible text encoding repair", () => {
  it("repairs Portuguese mojibake without changing normal text", () => {
    expect(repairVisibleText("ConfiguraÃ§Ã£o de frete")).toBe("Configuração de frete");
    expect(repairVisibleText("Texto normal")).toBe("Texto normal");
  });

  it("does not rewrite emoji or replacement-character text", () => {
    expect(repairVisibleText("ðŸŽ")).toBe("ðŸŽ");
    expect(repairVisibleText("Texto �")).toBe("Texto �");
  });
});
