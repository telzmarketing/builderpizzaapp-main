import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { ApiStrategicCampaign } from "@/lib/api";
import StrategicCampaignCommercialTab from "./StrategicCampaignCommercialTab";
import StrategicCampaignCapacityTab from "./StrategicCampaignCapacityTab";
import StrategicCampaignReservationsTab from "./StrategicCampaignReservationsTab";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    strategicCampaignsApi: {
      ...actual.strategicCampaignsApi,
      listCapacitySlots: vi.fn().mockResolvedValue([]),
      listReservations: vi.fn().mockResolvedValue([]),
    },
  };
});

const campaign: ApiStrategicCampaign = {
  id: "campaign-1",
  name: "Black Friday",
  commercial_name: "Black Friday",
  slug: "black-friday",
  description: null,
  status: "draft",
  starts_at: null,
  ends_at: null,
  visual_config: {},
  commercial_config: {
    sales_mode: "preorder",
    allow_when_store_closed: true,
    require_scheduled_order: true,
    min_lead_minutes: 30,
    max_lead_days: 15,
    allowed_payment_methods: ["pix"],
  },
  marketing_config: { planned_budget: null, traffic_campaign_id: null, attribution_window_days: 7 },
  published_version: null,
  offers: [],
};

describe("strategic campaign C6 admin tabs", () => {
  it("renders the editable commercial policy", () => {
    const html = renderToStaticMarkup(<StrategicCampaignCommercialTab campaign={campaign} onChanged={() => undefined} />);
    expect(html).toContain("Comercialização");
    expect(html).toContain("Venda antecipada");
    expect(html).toContain("Permitir venda com a loja fechada");
    expect(html).toContain("Salvar comercialização");
  });

  it("renders an explicit loading state for capacity", () => {
    const html = renderToStaticMarkup(<StrategicCampaignCapacityTab campaign={campaign} />);
    expect(html).toContain("Agendamento e capacidade");
    expect(html).toContain("Carregando horários e capacidades");
  });

  it("renders an explicit loading state and reservation actions", () => {
    const html = renderToStaticMarkup(<StrategicCampaignReservationsTab campaign={campaign} />);
    expect(html).toContain("Pedidos e reservas");
    expect(html).toContain("Processar vencidas");
    expect(html).toContain("Carregando reservas");
  });
});
