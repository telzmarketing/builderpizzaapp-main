import type { ApiStrategicCampaign, StrategicCampaignStatus } from "@/lib/api";

export type CampaignPeriodFilter = "all" | "current" | "upcoming" | "past" | "undated";

export const campaignStatusLabel = (status: StrategicCampaignStatus) => ({ draft: "Rascunho", scheduled: "Agendada", active: "Ativa", paused: "Pausada", sold_out: "Esgotada", ended: "Encerrada", archived: "Arquivada" })[status];

export function filterStrategicCampaigns(campaigns: ApiStrategicCampaign[], filters: { query: string; status: "all" | StrategicCampaignStatus; period: CampaignPeriodFilter }, now = new Date()) {
  const query = filters.query.trim().toLocaleLowerCase("pt-BR");
  const nowTime = now.getTime();
  return campaigns.filter((campaign) => {
    const matchesQuery = !query || [campaign.name, campaign.commercial_name, campaign.slug, campaign.description].some((value) => value?.toLocaleLowerCase("pt-BR").includes(query));
    const matchesStatus = filters.status === "all" || campaign.status === filters.status;
    const start = campaign.starts_at ? new Date(campaign.starts_at).getTime() : null;
    const end = campaign.ends_at ? new Date(campaign.ends_at).getTime() : null;
    const matchesPeriod = filters.period === "all" || (filters.period === "undated" && start === null && end === null) || (filters.period === "upcoming" && start !== null && start > nowTime) || (filters.period === "past" && end !== null && end < nowTime) || (filters.period === "current" && (start === null || start <= nowTime) && (end === null || end >= nowTime));
    return matchesQuery && matchesStatus && matchesPeriod;
  });
}

export function strategicCampaignSummary(campaigns: ApiStrategicCampaign[]) {
  return { total: campaigns.length, active: campaigns.filter((item) => item.status === "active").length, scheduled: campaigns.filter((item) => item.status === "scheduled").length, offers: campaigns.reduce((total, item) => total + item.offers.length, 0) };
}
