import { describe, expect, it } from "vitest";
import type { ApiStrategicCampaign, StrategicCampaignStatus } from "@/lib/api";
import { campaignStatusLabel, filterStrategicCampaigns, strategicCampaignSummary } from "./strategicCampaignAdmin";

function campaign(overrides: Partial<ApiStrategicCampaign> = {}): ApiStrategicCampaign {
  return {
    id: "campaign-1", name: "Black Friday", commercial_name: "Festival Black", slug: "black-friday", description: "Ofertas de novembro", status: "draft",
    starts_at: null, ends_at: null, visual_config: {}, published_version: null, offers: [],
    commercial_config: { sales_mode: "immediate", allow_when_store_closed: false, require_scheduled_order: false, min_lead_minutes: 0, max_lead_days: null, allowed_payment_methods: [] },
    marketing_config: { planned_budget: null, traffic_campaign_id: null, attribution_window_days: 30 },
    ...overrides,
  };
}

describe("strategic campaign admin helpers", () => {
  it("filters by text and status", () => {
    const data = [campaign(), campaign({ id: "2", name: "Natal", commercial_name: null, slug: "natal", description: null, status: "active" })];
    expect(filterStrategicCampaigns(data, { query: "festival", status: "draft", period: "all" })).toHaveLength(1);
    expect(filterStrategicCampaigns(data, { query: "natal", status: "active", period: "all" })[0]?.id).toBe("2");
  });

  it("filters current, future, past and undated periods", () => {
    const now = new Date("2026-11-25T12:00:00Z");
    const data = [
      campaign({ id: "current", starts_at: "2026-11-24T12:00:00Z", ends_at: "2026-11-26T12:00:00Z" }),
      campaign({ id: "future", starts_at: "2026-12-01T12:00:00Z" }),
      campaign({ id: "past", ends_at: "2026-11-20T12:00:00Z" }),
      campaign({ id: "undated" }),
    ];
    expect(filterStrategicCampaigns(data, { query: "", status: "all", period: "current" }, now).map((item) => item.id)).toEqual(["current", "undated"]);
    expect(filterStrategicCampaigns(data, { query: "", status: "all", period: "upcoming" }, now)[0]?.id).toBe("future");
    expect(filterStrategicCampaigns(data, { query: "", status: "all", period: "past" }, now)[0]?.id).toBe("past");
    expect(filterStrategicCampaigns(data, { query: "", status: "all", period: "undated" }, now)[0]?.id).toBe("undated");
  });

  it("summarizes campaigns and offers", () => {
    const data = [campaign({ status: "active", offers: [{ id: "o1" } as ApiStrategicCampaign["offers"][number]] }), campaign({ id: "2", status: "scheduled" })];
    expect(strategicCampaignSummary(data)).toEqual({ total: 2, active: 1, scheduled: 1, offers: 1 });
  });

  it("provides labels for every status", () => {
    const values: StrategicCampaignStatus[] = ["draft", "scheduled", "active", "paused", "sold_out", "ended", "archived"];
    expect(values.map(campaignStatusLabel)).toEqual(["Rascunho", "Agendada", "Ativa", "Pausada", "Esgotada", "Encerrada", "Arquivada"]);
  });
});
