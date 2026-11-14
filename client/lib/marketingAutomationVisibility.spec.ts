import { describe, expect, it } from "vitest";
import { countAutomationEntries, hasAutomationEntries } from "./marketingAutomationVisibility";

describe("marketing automation visibility", () => {
  it("counts marketing and chatbot automations without filtering inactive entries", () => {
    expect(countAutomationEntries([{ active: true }, { active: false }], [{ ativo: true }, { ativo: false }])).toBe(4);
  });

  it("keeps an inactive automation as a visible editable entry", () => {
    expect(hasAutomationEntries([{ ativo: false }])).toBe(true);
  });
});
