import { describe, expect, it } from "vitest";
import { ApiRequestError } from "@/lib/api";
import { contactRiskError } from "./CustomerContactRiskPanel";

describe("customer contact risk errors", () => {
  it("explains that the issue is the WhatsApp link, not the customer record", () => {
    expect(contactRiskError(new ApiRequestError("Cliente nao encontrado neste estabelecimento.", 404, "CustomerNotFound")))
      .toContain("não há vínculo WhatsApp válido neste estabelecimento");
  });

  it("normalizes the legacy backend message", () => {
    expect(contactRiskError(new Error("Cliente não encontrado neste estabelecimento.")))
      .toContain("não há vínculo WhatsApp válido neste estabelecimento");
  });
});
